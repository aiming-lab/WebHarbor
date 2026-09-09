from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_1.py"


class VerifyTask1Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--1",
                        "steps": ([{"url_after": "http://localhost:40016/product/IK-10002"}] if navigated else []),
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

    def test_correct_answer_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "The current price is $49.99, and it is not marked as a Local deal."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_product_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The current price is $49.99, and it is not marked as a Local deal.",
            navigated=False,
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_lack_product_page")

    def test_price_only_fails(self) -> None:
        returncode, verdict = self.run_verifier("It costs $49.99.")
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "answer_says_not_local_deal")

    def test_opposite_deal_claim_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "It costs $49.99 and it is marked as a Local deal."
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_missing_decimal_point_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "It costs $4999 and it is not a Local deal."
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
