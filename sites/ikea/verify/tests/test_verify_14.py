from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_14.py"


class VerifyTask14Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--14",
                        "steps": ([{"url": "http://localhost:40016/account/orders"}] if navigated else []),
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

    def test_correct_order_number_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "The most recent order number is IK-240055."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_orders_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The most recent order number is IK-240055.", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_carol_orders_page")

    def test_wrong_neighboring_order_fails(self) -> None:
        returncode, verdict = self.run_verifier("IK-240051")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_longer_number_does_not_match(self) -> None:
        returncode, verdict = self.run_verifier("IK-2400550")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
