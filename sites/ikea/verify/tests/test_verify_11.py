from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_11.py"


class VerifyTask11Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--11",
                        "steps": ([{"url": "http://localhost:40016/product/IK-10020"}] if navigated else []),
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

    def test_catalog_format_passes(self) -> None:
        returncode, verdict = self.run_verifier('The dimensions are 53x98".')
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_product_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier('The dimensions are 53x98".', navigated=False)
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_rosenmandel_product_page")

    def test_written_inches_and_multiplication_sign_passes(self) -> None:
        returncode, verdict = self.run_verifier("Dimensions: 53 × 98 inches.")
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_quotes_on_both_values_pass(self) -> None:
        returncode, verdict = self.run_verifier('It measures 53" x 98".')
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_wrong_dimensions_fail(self) -> None:
        returncode, verdict = self.run_verifier('It measures 57" x 98".')
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_missing_unit_fails(self) -> None:
        returncode, verdict = self.run_verifier("The dimensions are 53x98.")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
