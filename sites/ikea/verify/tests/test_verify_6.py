from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_6.py"


class VerifyTask6Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--6",
                        "steps": ([{"url": "http://localhost:40016/stores/brooklyn-ny"}] if navigated else []),
                        "final_answer": answer,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(VERIFIER), "--run_dir", str(run_dir)],
                capture_output=True,
                text=True,
            )
            return result.returncode, json.loads(result.stdout)

    def test_reset_empty_answer_fails(self) -> None:
        returncode, verdict = self.run_verifier("")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_both_amenities_pass(self) -> None:
        returncode, verdict = self.run_verifier(
            "The two amenities are Swedish Restaurant and Click & collect."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_store_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "Swedish Restaurant and Click & collect", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_brooklyn_store_page")

    def test_and_spelling_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "swedish restaurant; click and collect"
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_only_one_amenity_fails(self) -> None:
        returncode, verdict = self.run_verifier("Swedish Restaurant")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_wrong_amenities_fail(self) -> None:
        returncode, verdict = self.run_verifier("Planning studio and Returns desk")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
