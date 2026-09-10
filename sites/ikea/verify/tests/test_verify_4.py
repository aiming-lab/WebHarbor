from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_4.py"


class VerifyTask4Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--4",
                        "steps": ([{"url": "http://localhost:40016/product/IK-10023"}] if navigated else []),
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
            "The 5-year home protection plan lasts longer than the 3-year plan."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_product_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The 5-year home protection plan lasts longer.", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_knapper_product_page")

    def test_en_dash_spelling_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "5–year home protection is the longer option."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_wrong_plan_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The 3-year home protection plan is longer."
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_plan_mention_without_comparison_fails(self) -> None:
        returncode, verdict = self.run_verifier("There is a 5-year home protection plan.")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
