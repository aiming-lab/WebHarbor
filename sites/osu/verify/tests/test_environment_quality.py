"""Static, seed, registry, and grading-contract regressions for the OSU mirror."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

from _support import SEED, SITE, ensure_seed

ROOT = SITE.parents[1]
FORBIDDEN_RUBRIC_TOKENS = (
    "Anil Makhija",
    "Ryan Day",
    "Tom Ryan",
    "Beth Plale",
    "David Bickel",
    "James Cogdell",
    "William Farrar",
    "Yann Guezennec",
    "Jody Sheridan",
    "Covelli Center",
    "Ohio Stadium",
    "Value City Arena",
    "46,820",
    "32,820",
)


class EnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_seed()

    def test_site_registration_and_task_manifest(self):
        sites = re.search(r"SITES=\((.*?)\)", (ROOT / "websyn_start.sh").read_text(encoding="utf-8"), re.S).group(1).split()
        control_sites = next(
            ast.literal_eval(node.value)
            for node in ast.parse((ROOT / "control_server.py").read_text(encoding="utf-8")).body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SITES" for target in node.targets)
        )
        self.assertEqual(sites, control_sites)
        self.assertEqual(len(sites), len(set(sites)))
        self.assertEqual(sites.index("osu"), 20)
        self.assertIn(f"EXPOSE 8101 40000-{40000 + len(sites) - 1}", (ROOT / "Dockerfile").read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in (SITE / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 20)
        for index, row in enumerate(rows):
            self.assertEqual(row["id"], f"Ohio State University--{index}")
            self.assertEqual(row["web"], "http://localhost:40020/")
            self.assertTrue((ROOT / row["verifier_path"]).is_file())
            self.assertNotIn("answer", row)
            self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS:"))
            for token in FORBIDDEN_RUBRIC_TOKENS:
                self.assertNotIn(token, row["judge_rubric"], token)

    def test_real_image_manifest_and_files(self):
        manifest = json.loads((SITE / "image_sources.json").read_text(encoding="utf-8"))["images"]
        self.assertGreaterEqual(len(manifest), 19)
        allowed_pages = {
            "www.osu.edu",
            "undergrad.osu.edu",
            "fisher.osu.edu",
            "ohiostatebuckeyes.com",
            "cancer.osu.edu",
            "news.osu.edu",
        }
        references = (SITE / "app.py").read_text(encoding="utf-8") + "".join(
            path.read_text(encoding="utf-8") for path in (SITE / "templates").glob("*.html")
        )
        for item in manifest:
            with self.subTest(file=item["file"]):
                image = SITE / "static/images" / item["file"]
                self.assertTrue(image.is_file())
                self.assertGreater(image.stat().st_size, 5000)
                self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), item["output_sha256"])
                self.assertEqual(image.suffix, ".webp")
                self.assertIn(urlparse(item["source_page"]).hostname, allowed_pages)
                self.assertTrue(item["alt"].strip())
                self.assertIn(item["file"].removesuffix(".webp"), references)

    def test_seed_counts_and_constraints(self):
        connection = sqlite3.connect(SEED)
        try:
            expected = {
                "colleges": 16,
                "departments": 15,
                "programs": 20,
                "news_articles": 20,
                "events": 16,
                "research_centers": 15,
                "faculty": 15,
                "athletic_teams": 26,
                "users": 4,
                "bookmarks": 0,
            }
            self.assertEqual(
                {table: connection.execute(f"select count(*) from {table}").fetchone()[0] for table in expected},
                expected,
            )
            indexes = {row[1] for row in connection.execute("pragma index_list(bookmarks)")}
            self.assertTrue(any("bookmark" in name for name in indexes), indexes)
        finally:
            connection.close()

    def test_build_seed_generation_is_byte_deterministic(self):
        hashes = []
        with tempfile.TemporaryDirectory(prefix="osu-seed-") as tmp:
            for n in (1, 2):
                directory = Path(tmp) / str(n)
                directory.mkdir()
                for name in ("app.py", "seed_data.py", "image_sources.json", "migrate_seed.py"):
                    shutil.copy2(SITE / name, directory / name)
                subprocess.run(
                    [sys.executable, "migrate_seed.py"],
                    cwd=directory,
                    check=True,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONHASHSEED": "0"},
                )
                database = directory / "instance_seed/osu.db"
                hashes.append(hashlib.sha256(database.read_bytes()).hexdigest())
        self.assertEqual(hashes[0], hashes[1])

    def test_build_seed_preserves_existing_runtime(self):
        with tempfile.TemporaryDirectory(prefix="osu-live-preserve-") as tmp:
            directory = Path(tmp)
            for name in ("app.py", "seed_data.py", "image_sources.json", "migrate_seed.py"):
                shutil.copy2(SITE / name, directory / name)
            (directory / "instance").mkdir()
            runtime = directory / "instance/osu.db"
            shutil.copy2(SEED, runtime)
            with sqlite3.connect(runtime) as connection:
                connection.execute("UPDATE users SET full_name='Preserved local user' WHERE id=1")
            before = hashlib.sha256(runtime.read_bytes()).hexdigest()
            subprocess.run(
                [sys.executable, "migrate_seed.py"],
                cwd=directory,
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": "0"},
            )
            self.assertEqual(hashlib.sha256(runtime.read_bytes()).hexdigest(), before)
            self.assertTrue((directory / "instance_seed/osu.db").is_file())

    def test_post_forms_have_csrf(self):
        missing = []
        for path in (SITE / "templates").glob("*.html"):
            lines = path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if "<form" in line and 'method="post"' in line.lower() and not any(
                    token in "\n".join(lines[index : index + 8]) for token in ("csrf_token", "hidden_tag")
                ):
                    missing.append(f"{path.name}:{index + 1}")
        self.assertEqual(missing, [])

    def test_ui_responsive_controls_present(self):
        base = (SITE / "templates/base.html").read_text(encoding="utf-8")
        self.assertIn(".detail-layout", base)
        self.assertIn("overflow-x: auto", base)
        self.assertIn('aria-current="page"', base)
        self.assertNotIn("url_for('logout') }}\">", base)
        for name in (
            "athletics_team.html",
            "event_detail.html",
            "faculty_profile.html",
            "program_detail.html",
            "research_center.html",
            "department_detail.html",
        ):
            self.assertIn('class="detail-layout"', (SITE / "templates" / name).read_text(encoding="utf-8"), name)

    def test_all_read_only_verifiers_compare_complete_database(self):
        for index in range(20):
            self.assertIn("check_read_only", (SITE / f"verify/verify_{index}.py").read_text(encoding="utf-8"), index)

    def test_listing_templates_do_not_embed_detail_facts(self):
        athletics = (SITE / "templates/athletics.html").read_text(encoding="utf-8")
        self.assertNotIn("team.recent_record", athletics)
        self.assertNotIn("team.national_titles", athletics)
        research = (SITE / "templates/research.html").read_text(encoding="utf-8")
        self.assertNotIn("center.director", research)
        self.assertNotIn("center.founded_year", research)
        self.assertNotIn("center.focus_areas", research)
        programs = (SITE / "templates/programs.html").read_text(encoding="utf-8")
        self.assertNotIn("prog.units", programs)
        self.assertNotIn("prog.application_deadline", programs)
        self.assertNotIn("prog.gre_required", programs)
        departments = (SITE / "templates/departments.html").read_text(encoding="utf-8")
        self.assertNotIn("dept.chair", departments)
        self.assertNotIn("dept.location", departments)


if __name__ == "__main__":
    unittest.main()
