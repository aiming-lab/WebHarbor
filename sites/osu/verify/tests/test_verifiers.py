"""Positive and adversarial tests for all OSU verifiers."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import SEED, SITE, ensure_seed

VERIFY_DIR = SITE / "verify"
BASE = "http://localhost:40020"


def url(path: str) -> str:
    return BASE + path


def nav(path: str) -> dict:
    return {"url": url(path), "action": "navigate", "params": {}}


def click(src: str, dst: str) -> dict:
    return {"url": url(src), "url_after": url(dst), "action": "click", "params": {}}


def trans(src: str, dst: str) -> list[dict]:
    return [click(src, dst), nav(dst)]


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_seed()

    def run_verifier(self, task, steps, answer, mutate=None, task_id=None):
        with tempfile.TemporaryDirectory(prefix=f"osu-v-{task}-") as directory:
            root = Path(directory)
            initial = root / "initial.db"
            after = root / "after.db"
            run = root / "run"
            run.mkdir()
            shutil.copy2(SEED, initial)
            shutil.copy2(SEED, after)
            if mutate:
                connection = sqlite3.connect(after)
                try:
                    mutate(connection)
                    connection.commit()
                finally:
                    connection.close()
            trajectory = {
                "task_id": task_id or f"Ohio State University--{task}",
                "start_url": url("/"),
                "steps": steps,
                "final_url": (
                    steps[-1].get("url_after", steps[-1].get("url")) if steps else url("/")
                ),
                "final_answer": answer,
            }
            (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_DIR / f"verify_{task}.py"),
                    "--run_dir",
                    str(run),
                    "--initial_db",
                    str(initial),
                    "--after_db",
                    str(after),
                    "--no_llm",
                    "true",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            try:
                verdict = json.loads(result.stdout)
            except Exception as exc:  # noqa: BLE001
                self.fail(f"task {task}: stdout={result.stdout!r} stderr={result.stderr!r} {exc}")
            return result.returncode, verdict

    def positive(self, index: int):
        football = "/athletics/ohio-state-buckeyes-football"
        wrestling = "/athletics/ohio-state-buckeyes-wrestling"
        basketball = "/athletics/ohio-state-buckeyes-mens-basketball"
        fencing = "/athletics/ohio-state-buckeyes-fencing"
        cases = {
            0: ([nav("/")] + trans("/", "/academics"), "Fisher College of Business dean is Anil Makhija."),
            1: ([nav("/about")], "Varsity Sports: 36."),
            2: (
                [nav("/athletics")] + trans("/athletics", football) + [nav("/athletics")] + trans("/athletics", wrestling),
                "Football and wrestling both list the Big Ten.",
            ),
            3: ([nav("/athletics")] + trans("/athletics", football), "Head coach Ryan Day; recent record 11-2."),
            4: (
                [nav("/search?q=research+expenditures")]
                + trans(
                    "/search?q=research+expenditures",
                    "/news/ohio-state-sets-record-for-research-expenditures-at-13-billion",
                ),
                "$1.3 billion; September 23, 2024.",
            ),
            5: ([nav("/about")], "Founded in 1870 as Ohio Agricultural and Mechanical College."),
            6: (
                [nav("/research")] + trans("/research", "/research/translational-data-analytics-institute"),
                "Director Beth Plale; Data analytics, Machine learning, Health informatics, Social science.",
            ),
            7: ([nav("/about")], "Undergraduate: 46,820; graduate students: 14,000; difference: 32,820."),
            8: ([nav("/academics")], "Engineering: 8,000; Fisher: 4,500; Engineering has more, by 3,500."),
            9: ([nav("/programs?college=engineering")], "There are 3 distinct types: BS, MS, and PhD."),
            10: ([nav("/athletics")] + trans("/athletics", wrestling), "Head coach Tom Ryan; home venue Covelli Center."),
            11: (
                [nav("/research")] + trans("/research", "/research/ohio-supercomputer-center"),
                "Director David Bickel; founded 1987.",
            ),
            12: (
                [nav("/programs?q=Juris+Doctor")]
                + trans("/programs?q=Juris+Doctor", "/programs/juris-doctor-jd"),
                "JD; 90 credits; 3 years.",
            ),
            13: (
                [nav("/departments")] + trans("/departments", "/departments/department-of-mathematics"),
                "Chair James Cogdell; location 100 Mathematics Building.",
            ),
            14: (
                [nav("/athletics")]
                + trans("/athletics", football)
                + [nav("/athletics")]
                + trans("/athletics", basketball),
                "Football: Ohio Stadium; basketball: Value City Arena.",
            ),
            15: (
                [nav("/athletics")]
                + trans("/athletics", wrestling)
                + [nav("/athletics")]
                + trans("/athletics", fencing),
                "Wrestling: 8; fencing: 2; wrestling has more by 6.",
            ),
            16: (
                [nav("/programs?degree=MBA")]
                + trans("/programs?degree=MBA", "/programs/master-of-business-administration-mba"),
                "Deadline April 1; 60 credits; GRE not required.",
            ),
            17: (
                [nav("/search?q=cancer+research")]
                + trans(
                    "/search?q=cancer+research",
                    "/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy",
                ),
                "Ohio State Researchers Develop Breakthrough Cancer Immunotherapy by Jody Sheridan.",
            ),
            18: (
                [nav("/research")]
                + trans("/research", "/research/james-cancer-hospital-and-solove-research-institute"),
                "Director William Farrar; Cancer research, Oncology, Clinical trials, Precision medicine.",
            ),
            19: (
                [nav("/research")] + trans("/research", "/research/center-for-clean-hydrogen"),
                "Director Yann Guezennec; founded 2022; Hydrogen energy, Fuel cells, Green hydrogen, Energy storage.",
            ),
        }
        return cases[index]

    def test_all_positive(self):
        for index in range(20):
            with self.subTest(i=index):
                steps, answer = self.positive(index)
                returncode, verdict = self.run_verifier(index, steps, answer)
                self.assertEqual(returncode, 0, verdict)

    def test_noop_empty_answer_fails(self):
        for index in range(20):
            with self.subTest(i=index):
                returncode, verdict = self.run_verifier(index, [nav("/")], "")
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "final_answer_nonempty")

    def test_shortcut_answer_only_fails(self):
        for index in range(20):
            with self.subTest(i=index):
                _, answer = self.positive(index)
                returncode, verdict = self.run_verifier(index, [], answer)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])

    def test_wrong_task_id_fails(self):
        for index in range(20):
            with self.subTest(i=index):
                steps, answer = self.positive(index)
                returncode, verdict = self.run_verifier(
                    index, steps, answer, task_id="Ohio State University--999"
                )
                self.assertNotEqual(returncode, 0)
                self.assertEqual(verdict["reason"], "task_id_matches")

    def test_external_origin_fails(self):
        returncode, verdict = self.run_verifier(
            1,
            [{"url": "https://evil.invalid/about", "action": "navigate", "params": {}}],
            "Varsity Sports: 36.",
        )
        self.assertNotEqual(returncode, 0)
        self.assertFalse(verdict["pass"])

    def test_database_mutation_fails_all(self):
        def mutate(connection):
            connection.execute("UPDATE news_articles SET view_count=view_count+1 WHERE id=1")

        for index in range(20):
            with self.subTest(i=index):
                steps, answer = self.positive(index)
                returncode, verdict = self.run_verifier(index, steps, answer, mutate)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])

    def test_negated_answers_fail(self):
        cases = {
            1: "There are not 36 varsity sports.",
            3: "Ryan Day is not coach; record 11-2.",
            5: "It was not founded in 1870 as Ohio Agricultural and Mechanical College.",
            16: "Deadline is not April 1; 60 credits; GRE not required.",
        }
        for index, answer in cases.items():
            with self.subTest(i=index):
                steps, _ = self.positive(index)
                returncode, verdict = self.run_verifier(index, steps, answer)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])

    def test_wrong_answers_fail(self):
        cases = {
            0: "Fisher College of Business dean is Patricia Bauer.",
            4: "$2.1 billion; September 23, 2024.",
            6: "Director Beth Plale; Data analytics only.",
            9: "There are 3 distinct types: BA, MA, and MBA.",
            10: "Head coach Ryan Day; home venue Ohio Stadium.",
            11: "Director Beth Plale; founded 1987.",
            12: "JD; 120 credits; 4 years.",
            13: "Chair Claudia Turro; location Evans 100D.",
            16: "Deadline March 1; 60 credits; GRE required.",
            17: "Ohio State Researchers Develop Breakthrough Cancer Immunotherapy by OSU News Staff.",
            18: "Director William Farrar; Hydrogen energy, Fuel cells, Green hydrogen, Energy storage.",
            19: "Director Yann Guezennec; founded 1987; Data analytics, Machine learning, Health informatics, Social science.",
        }
        for index, answer in cases.items():
            with self.subTest(i=index):
                steps, _ = self.positive(index)
                returncode, verdict = self.run_verifier(index, steps, answer)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])

    def test_swapped_comparisons_fail(self):
        cases = {
            7: "Undergraduate: 14,000; graduate: 46,820; difference 32,820.",
            8: "Engineering: 4,500; Fisher: 8,000; Engineering has more by 3,500.",
            14: "Football: Value City Arena; basketball: Ohio Stadium.",
            15: "Wrestling: 2; fencing: 8; wrestling has more by 6.",
        }
        for index, answer in cases.items():
            with self.subTest(i=index):
                steps, _ = self.positive(index)
                returncode, verdict = self.run_verifier(index, steps, answer)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])

    def test_required_filters_fail_when_missing(self):
        for index in (9, 12, 16):
            with self.subTest(i=index):
                steps, answer = self.positive(index)
                steps = [
                    item
                    for item in steps
                    if "?" not in item.get("url", "") and "?" not in item.get("url_after", "")
                ]
                returncode, verdict = self.run_verifier(index, steps, answer)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])

    def test_listing_without_detail_is_shortcut(self):
        shortcuts = {
            3: [nav("/athletics")],
            6: [nav("/research")],
            10: [nav("/athletics")],
            11: [nav("/research")],
            13: [nav("/departments")],
            18: [nav("/research")],
            19: [nav("/research")],
        }
        for index, steps in shortcuts.items():
            with self.subTest(i=index):
                _, answer = self.positive(index)
                returncode, verdict = self.run_verifier(index, steps, answer)
                self.assertNotEqual(returncode, 0)
                self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
