"""Contract checks for the instructure contribution: tasks.jsonl schema, seed
integrity, asset inventory, and registration consistency."""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import unittest
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1]
ROOT = SITE_DIR.parents[1]


class TaskContractTests(unittest.TestCase):
    def setUp(self):
        self.rows = [json.loads(line)
                     for line in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_task_schema(self):
        self.assertEqual(len(self.rows), 30)
        contributor_keys = ["web_name", "id", "ques", "web", "upstream_url"]
        reviewer_keys = ["verifier_path", "judge_rubric"]
        for row in self.rows:
            # Five contributor keys + the reviewer-appended grading-contract keys
            # (see verify/README.md); nothing else may appear.
            self.assertEqual(sorted(row.keys()), sorted(contributor_keys + reviewer_keys),
                             row.get("id"))
            self.assertNotIn("answer", row)
            self.assertNotIn("Answer", "".join(row.keys()))

    def test_task_grading_keys(self):
        for i, row in enumerate(self.rows):
            self.assertEqual(row["verifier_path"],
                             f"sites/instructure/verify/verify_{i}.py",
                             row.get("id"))
            self.assertTrue((ROOT / row["verifier_path"]).is_file(),
                            row["verifier_path"])
            self.assertIn("FACT CHECKPOINTS", row["judge_rubric"])
            self.assertIn("Empty answer = FAIL", row["judge_rubric"])

    def test_task_ids_and_web(self):
        for i, row in enumerate(self.rows):
            self.assertEqual(row["id"], f"Instructure--{i}")
            self.assertEqual(row["web"], "http://localhost:40077/")
            self.assertEqual(row["upstream_url"], "https://www.instructure.com/")
            self.assertEqual(row["web_name"], "Instructure")

    def test_task_questions_are_navigation_tasks(self):
        verbs = ("Open", "Browse", "Search", "Go", "Use", "Compare", "Sign", "Create",
                 "On the", "In the", "Navigate", "Visit", "Apply", "Read", "Explore",
                 "Uncheck", "Filter", "Attend", "Remove")
        for row in self.rows:
            self.assertTrue(any(row["ques"].strip().startswith(v) for v in verbs),
                            f"{row['id']}: question lacks an actionable opening")


class SeedIntegrityTests(unittest.TestCase):
    def test_seeded_database_counts(self):
        db_path = SITE_DIR / "instance" / "instructure.db"
        self.assertTrue(db_path.exists(), "instance/instructure.db missing")
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        resources = cur.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        events = cur.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        press = cur.execute("SELECT COUNT(*) FROM resources WHERE type='press_release'").fetchone()[0]
        users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        con.close()
        self.assertEqual(resources, 700)
        self.assertEqual(events, 39)
        self.assertGreaterEqual(press, 150)
        self.assertGreaterEqual(users, 4)

    def test_source_snapshots_track_catalog(self):
        resources = json.loads((SITE_DIR / "source_data_resources.json").read_text(encoding="utf-8"))
        self.assertEqual(len(resources), 700)
        misc = json.loads((SITE_DIR / "source_data_misc.json").read_text(encoding="utf-8"))
        self.assertEqual(len(misc.get("events", [])), 39)
        self.assertEqual(len(misc.get("jobs", [])), 43)
        self.assertEqual(len(misc.get("leaders", [])), 10)


class AssetInventoryTests(unittest.TestCase):
    def test_inventory_matches_disk(self):
        inv = json.loads((SITE_DIR / "asset_inventory.json").read_text(encoding="utf-8"))
        for asset in inv["assets"]:
            path = SITE_DIR / asset["path"]
            self.assertTrue(path.exists(), asset["path"])
            self.assertEqual(path.stat().st_size, asset["bytes"], asset["path"])

    def test_inventory_covers_all_managed_images(self):
        inv = json.loads((SITE_DIR / "asset_inventory.json").read_text(encoding="utf-8"))
        listed = {a["path"] for a in inv["assets"]}
        for path in (SITE_DIR / "static" / "images").rglob("*"):
            if path.is_file() and path.name != ".gitkeep":
                self.assertIn(path.relative_to(SITE_DIR).as_posix(), listed, path)

    def test_no_placeholder_media(self):
        inv = json.loads((SITE_DIR / "asset_inventory.json").read_text(encoding="utf-8"))
        for asset in inv["assets"]:
            self.assertFalse(re.search(r"placeholder|dummy|sample", asset["path"], re.I),
                             asset["path"])
            self.assertTrue(
                asset["source_url"].startswith(
                    ("https://www.instructure.com/", "https://live-inst.pantheonsite.io/")),
                asset["path"])


class RegistrationTests(unittest.TestCase):
    def test_startup_lists_site(self):
        startup = (ROOT / "websyn_start.sh").read_text(encoding="utf-8")
        self.assertRegex(startup, r"\binstructure\b")

    def test_control_server_lists_site(self):
        control = (ROOT / "control_server.py").read_text(encoding="utf-8")
        self.assertRegex(control, r"'instructure'")

    def test_dockerfile_builds_seed(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("/opt/WebSyn/instructure", docker)
        self.assertIn("check_asset_inventory.py /opt/WebSyn/instructure", docker)
        self.assertRegex(docker, r"EXPOSE 8101 40000-400\d\d")

    def test_readme_row_declares_assigned_port(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertRegex(readme, r"\| Instructure \| 40077 \|")


if __name__ == "__main__":
    unittest.main()
