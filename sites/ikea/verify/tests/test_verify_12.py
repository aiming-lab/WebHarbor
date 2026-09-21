from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_12.py"


class VerifyTask12Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--12",
                        "steps": ([{"url": "http://localhost:40016/support/pickup-readiness-notifications"}] if navigated else []),
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

    def test_exact_pickup_passes(self) -> None:
        returncode, verdict = self.run_verifier("Pickup")
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_article_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier("Pickup", navigated=False)
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_pickup_readiness_article")

    def test_category_sentence_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "The help category shown is Pickup."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_under_pickup_passes(self) -> None:
        returncode, verdict = self.run_verifier("The article is under Pickup.")
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_question_restatement_with_wrong_category_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The pickup readiness article has the Delivery category."
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_wrong_category_fails(self) -> None:
        returncode, verdict = self.run_verifier("Category: Delivery")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
