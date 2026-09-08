"""Exercise the public subprocess contract, using explicitly synthetic runs."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_read_tasks as fixtures


class VerifierEntryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SyntheticReadTaskTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.check(2)
        self.run_dir = self.fixture.run_dir
        self.other_cwd = tempfile.TemporaryDirectory()
        self.addCleanup(self.other_cwd.cleanup)

    def invoke(self, number=2):
        result = subprocess.run(
            [sys.executable, str(fixtures.SITE / "verify" / f"verify_{number}.py"),
             "--run_dir", str(self.run_dir)],
            cwd=self.other_cwd.name, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.stderr, "")
        verdict = json.loads(result.stdout)
        self.assertEqual(verdict["task_id"], f"IMDb--{number}")
        self.assertIsInstance(verdict["pass"], bool)
        return result.returncode, verdict

    def test_only_absolute_run_dir_argument_works_from_another_cwd(self):
        code, verdict = self.invoke()
        self.assertEqual(code, 0)
        self.assertTrue(verdict["pass"])

    def test_missing_after_snapshot_never_falls_back_to_live_database(self):
        (self.run_dir / "after.db").unlink()
        code, verdict = self.invoke()
        self.assertEqual(code, 1)
        self.assertFalse(verdict["pass"])
        self.assertIn("Missing after", verdict["reason"])

    def test_same_id_old_question_is_not_current_candidate_evidence(self):
        path = self.run_dir / "trajectory.json"
        trajectory = json.loads(path.read_text())
        trajectory["task"] = "Old question with weaker requirements"
        path.write_text(json.dumps(trajectory))
        code, verdict = self.invoke()
        self.assertEqual(code, 1)
        self.assertFalse(verdict["pass"])
        self.assertIn("question", verdict["reason"])

    def test_every_task_entry_rejects_another_task_or_missing_artifacts(self):
        (self.run_dir / "after.db").unlink()
        for task_id in fixtures.TASKS:
            number = int(task_id.split("--")[1])
            with self.subTest(task_id=task_id):
                code, verdict = self.invoke(number)
                self.assertEqual(code, 1)
                self.assertFalse(verdict["pass"])

    def test_current_tasks_and_numbered_entries_are_one_to_one(self):
        expected = {0, 2, 7, 9, 10, 12, 14, 15, 16, 17}
        task_numbers = {int(task_id.split("--")[1]) for task_id in fixtures.TASKS}
        entries = {int(path.stem.split("_")[1])
                   for path in (fixtures.SITE / "verify").glob("verify_[0-9]*.py")}
        self.assertEqual(task_numbers, expected)
        self.assertEqual(entries, expected)
        self.assertEqual(fixtures.read_tasks.READ_TASKS, expected - {15, 16, 17})


if __name__ == "__main__":
    unittest.main()
