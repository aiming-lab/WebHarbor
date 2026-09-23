"""Regression contract for the Versus mirror.

Each test pins a defect found during review, so a later change that reintroduces
it fails here instead of in a benchmark run.

Run from the repo root:
    docker run --rm -v "$PWD:/repo:ro" -w /repo wh-review025-deps:latest \
        python3 -m unittest discover -s sites/versus/tests -v
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath

SITE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SITE_DIR.parents[1]
TASKS = SITE_DIR / "tasks.jsonl"
SITE_NAME = "versus"


def load_tasks():
    return [json.loads(line) for line in TASKS.read_text().splitlines() if line.strip()]


def build_seed(dest: Path) -> Path:
    """Generate the seed DB the way the Dockerfile does, into an isolated copy."""
    work = dest / SITE_NAME
    shutil.copytree(SITE_DIR, work)
    for sub in ("instance", "instance_seed"):
        shutil.rmtree(work / sub, ignore_errors=True)
    subprocess.run([sys.executable, "-c", "from app import app"],
                   cwd=work, check=True, capture_output=True)
    return work / "instance" / f"{SITE_NAME}.db"


class SeedDeterminism(unittest.TestCase):
    """F9: two builds of the same commit must ship byte-identical seed data."""

    def test_seed_is_byte_reproducible(self):
        digests = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                db = build_seed(Path(tmp))
                digests.append(hashlib.sha256(db.read_bytes()).hexdigest())
        self.assertEqual(
            digests[0], digests[1],
            "seed DB differs between builds; a random salt or other nondeterminism "
            "leaked into instance_seed, so its hash cannot be pinned",
        )


class RegistryConsistency(unittest.TestCase):
    def _sites_from_control_server(self):
        text = (REPO_ROOT / "control_server.py").read_text()
        block = re.search(r"^SITES = \[(.*?)\]", text, re.S | re.M).group(1)
        return re.findall(r"'([a-z0-9_]+)'", block)

    def _sites_from_start_script(self):
        text = (REPO_ROOT / "websyn_start.sh").read_text()
        block = re.search(r"^SITES=\((.*?)\)", text, re.S | re.M).group(1)
        return block.split()

    def test_site_registered_identically_in_both_registries(self):
        control = self._sites_from_control_server()
        start = self._sites_from_start_script()
        self.assertEqual(control, start, "control_server and websyn_start site order differ")
        self.assertIn(SITE_NAME, control)

    def test_task_urls_match_the_registered_port(self):
        port = 40000 + self._sites_from_control_server().index(SITE_NAME)
        for task in load_tasks():
            self.assertEqual(
                f"http://localhost:{port}/", task["web"],
                f"{task['id']} points at {task['web']} but the site is registered on {port}",
            )

    def test_dockerfile_exposes_the_registered_port(self):
        text = (REPO_ROOT / "Dockerfile").read_text()
        upper = int(re.search(r"EXPOSE 8101 40000-(\d+)", text).group(1))
        port = 40000 + self._sites_from_control_server().index(SITE_NAME)
        self.assertGreaterEqual(upper, port)


class TaskContract(unittest.TestCase):
    def test_every_task_has_a_verifier_and_rubric(self):
        for task in load_tasks():
            self.assertTrue(task.get("verifier_path"), f"{task['id']} has no verifier_path")
            self.assertTrue((REPO_ROOT / task["verifier_path"]).exists(),
                            f"{task['id']}: {task['verifier_path']} does not exist")
            self.assertTrue(task.get("judge_rubric"), f"{task['id']} has no judge_rubric")

    def test_task_file_carries_no_answer_key(self):
        allowed = {"web_name", "id", "ques", "web", "upstream_url",
                   "verifier_path", "judge_rubric"}
        for task in load_tasks():
            extra = set(task) - allowed
            self.assertFalse(extra, f"{task['id']} carries unexpected keys {extra}")
            self.assertNotIn("answer", task)

    def test_task_ids_are_contiguous_and_unique(self):
        ids = [t["id"] for t in load_tasks()]
        self.assertEqual(len(ids), len(set(ids)), "duplicate task ids")
        self.assertEqual(ids, [f"Versus--{i}" for i in range(len(ids))])

    def test_verify_dir_holds_exactly_the_expected_files(self):
        """A rename left 16 stray "verify_N 2.py" copies in the directory once.

        They were never committed, but they crashed the adversarial harness,
        which globs the directory to decide what to grade. A directory that is
        the input to grading has to be exactly what it claims.
        """
        vd = SITE_DIR / "verify"
        expected = {f"verify_{i}.py" for i in range(len(load_tasks()))} | {"verify_lib.py"}
        actual = {p.name for p in vd.iterdir() if p.is_file() and p.suffix == ".py"}
        self.assertEqual(actual, expected,
                         f"unexpected: {sorted(actual - expected)}; "
                         f"missing: {sorted(expected - actual)}")

    def test_task_count_is_in_the_review_guide_range(self):
        self.assertGreaterEqual(len(load_tasks()), 15)
        self.assertLessEqual(len(load_tasks()), 20)


class StatefulTasksStartUnsatisfied(unittest.TestCase):
    """T1: a task that asks the agent to create state must not already be satisfied."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db = build_seed(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def saved_pairs(self, email):
        con = sqlite3.connect(self.db)
        try:
            rows = con.execute(
                "SELECT l.slug, r.slug FROM saved_comparison sc "
                "JOIN user u ON u.id = sc.user_id "
                "JOIN product l ON l.id = sc.left_id "
                "JOIN product r ON r.id = sc.right_id WHERE u.email = ?",
                (email,)).fetchall()
        finally:
            con.close()
        return {frozenset(pair) for pair in rows}

    def test_save_tasks_target_a_pair_not_already_saved(self):
        existing = self.saved_pairs("alice.j@test.com")
        slugs = {p[0] for p in sqlite3.connect(self.db).execute(
            "SELECT slug FROM product")}
        for task in load_tasks():
            ques = task["ques"].lower()
            if "save" not in ques:
                continue
            mentioned = frozenset(s for s in slugs
                                  if s.replace("-", " ") in ques.replace("-", " "))
            if len(mentioned) != 2:
                continue
            self.assertNotIn(
                mentioned, existing,
                f"{task['id']} asks to save a comparison Alice already has at seed "
                f"state, so the after-state is identical whether or not the agent acts",
            )


class SourceBackedImages(unittest.TestCase):
    """Every entity image is local, exact, hashed and traceable to a source page."""

    def _inventory(self):
        return json.loads((SITE_DIR / "asset_inventory.json").read_text())

    def _run_gate(self, site: Path):
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_asset_inventory.py"), str(site)],
            capture_output=True,
            text=True,
        )

    def test_source_backed_assets_pass_the_repository_gate(self):
        inventory = self._inventory()
        self.assertEqual(inventory["schema_version"], 1)
        self.assertEqual(inventory["asset_count"], 107)
        self.assertEqual(len(inventory["assets"]), 107)
        run = self._run_gate(SITE_DIR)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_every_image_has_entity_and_source_provenance(self):
        for row in self._inventory()["assets"]:
            self.assertEqual(PurePosixPath(row["path"]).suffix, ".webp")
            self.assertTrue(row["entity_name"])
            self.assertTrue(row["source_page"].startswith("https://"))
            self.assertTrue(row["source_url"].startswith("https://"))
            self.assertTrue(row["source_sha256"])
            self.assertTrue(row["license"])

    def test_gate_rejects_a_tampered_tile(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / SITE_NAME
            shutil.copytree(SITE_DIR, work)
            victim = work / self._inventory()["assets"][0]["path"]
            victim.write_bytes(victim.read_bytes() + b"tamper")
            run = self._run_gate(work)
            self.assertNotEqual(run.returncode, 0,
                             "gate passed a tampered tile; its PASS means nothing")

    def test_every_product_has_a_tile(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = build_seed(Path(tmp))
            slugs = {r[0] for r in sqlite3.connect(db).execute("SELECT slug FROM product")}
        listed = {PurePosixPath(row["path"]).stem for row in json.loads(
            (SITE_DIR / "asset_inventory.json").read_text())["assets"]}
        self.assertEqual(slugs, listed, "product catalogue and tile inventory disagree")


class VisualTaskPathStructure(unittest.TestCase):
    """Pin the task-path presentation fixes found in the visual audit."""

    def test_navigation_has_a_compact_mobile_variant(self):
        base = (SITE_DIR / "templates" / "base.html").read_text()
        css = (SITE_DIR / "static" / "css" / "main.css").read_text()
        self.assertIn('<details class="mobile-menu">', base)
        self.assertIn(".desktop-nav { display: none; }", css)
        self.assertIn(".mobile-menu-panel", css)

    def test_mobile_comparison_values_are_labelled_and_stackable(self):
        compare = (SITE_DIR / "templates" / "compare.html").read_text()
        css = (SITE_DIR / "static" / "css" / "main.css").read_text()
        for label in ('data-label="{{ left.name }}"',
                      'data-label="{{ right.name }}"',
                      'data-label="Margin"'):
            self.assertIn(label, compare)
        self.assertIn("content: attr(data-label)", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)

    def test_homepage_exposes_real_scale_and_image_backed_pairs(self):
        index = (SITE_DIR / "templates" / "index.html").read_text()
        self.assertIn("catalogue-summary", index)
        self.assertIn("comparison pairs", index)
        self.assertIn("pair-media", index)
        self.assertIn("Top rated by category", index)


class VerifierTerminalState(unittest.TestCase):
    """An independent reviewer caught a run that answered from a crash page.

    Every other check passed it: the facts had been read, the answer was right,
    and nothing in the bundle said the browser had failed. Evidence that hides
    its own failure must not grade as clean.
    """

    def _lib(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "versus_verify_lib", SITE_DIR / "verify" / "verify_lib.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_answer_from_an_error_page_is_not_on_site(self):
        V = self._lib()
        # The origin comes from the run's own start_url, so a registry re-slot
        # does not expire recorded evidence. An arbitrary port is used here on
        # purpose: the check is internal consistency, not today's port.
        base = "http://localhost:40123"
        ok = {"start_url": f"{base}/",
              "steps": [{"step": 0, "action": "click", "url": f"{base}/"},
                        {"step": 1, "action": "done",
                         "url": f"{base}/item/nikon-z8"}]}
        crashed = {"start_url": f"{base}/",
                   "steps": [{"step": 0, "action": "click", "url": f"{base}/"},
                             {"step": 1, "action": "done",
                              "url": "chrome-error://chromewebdata/"}]}
        self.assertTrue(V.answered_on_site(ok))
        self.assertFalse(V.answered_on_site(crashed),
                         "a final answer emitted from a browser error page counted as on-site")
        self.assertFalse(V.answered_on_site({"start_url": f"{base}/", "steps": []}))
        self.assertFalse(V.answered_on_site({"steps": ok["steps"]}),
                         "a trajectory with no start_url has no origin to be consistent with")

    def test_a_run_survives_the_site_being_re_slotted(self):
        """Recorded evidence must not expire when upstream moves the port."""
        V = self._lib()
        old = {"start_url": "http://localhost:40027/",
               "steps": [{"step": 0, "action": "click", "url": "http://localhost:40027/"},
                         {"step": 1, "action": "done",
                          "url": "http://localhost:40027/item/nikon-z8"}]}
        self.assertTrue(V.answered_on_site(old))
        self.assertTrue(V.navigated_to(old, "/item/nikon-z8"))

    def test_every_verifier_checks_the_terminal_state(self):
        for path in sorted((SITE_DIR / "verify").glob("verify_*.py")):
            if path.name == "verify_lib.py":
                continue
            src = path.read_text()
            self.assertTrue(
                "terminal_state_is_sound" in src or "answered_on_site" in src,
                f"{path.name} does not check where the answer was emitted from")


class UiDisclosureRemoved(unittest.TestCase):
    """Repository disclosures must not be rendered in the site UI."""

    def test_templates_do_not_render_repository_disclosures(self):
        forbidden = (
            "not affiliated",
            "synthetic",
            "benchmark mirror",
            "offline mirror",
            "webharbor",
            "source-backed",
            "versus.com",
        )
        for template in sorted((SITE_DIR / "templates").glob("*.html")):
            text = template.read_text().lower()
            for token in forbidden:
                self.assertNotIn(token, text, f"{template.name} renders disclosure token {token}")

    def test_notice_exists_and_covers_imagery_and_data(self):
        notice = (SITE_DIR / "NOTICE.md").read_text().lower()
        for token in ("non-affiliation", "synthetic", "removal", "versus score"):
            self.assertIn(token, notice, f"NOTICE.md does not cover {token}")


class CsrfProtection(unittest.TestCase):
    """F10: 23 of 25 sites on main install CSRFProtect; this one must too."""

    def test_app_installs_csrf_protection(self):
        source = (SITE_DIR / "app.py").read_text()
        self.assertIn("CSRFProtect", source)

    def test_state_changing_forms_carry_a_token(self):
        for template in ("compare.html", "login.html"):
            text = (SITE_DIR / "templates" / template).read_text()
            if "method=\"post\"" not in text.lower():
                continue
            self.assertIn("csrf_token", text,
                          f"{template} posts without a CSRF token field")


if __name__ == "__main__":
    unittest.main()
