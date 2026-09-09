from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_9.py"


class VerifyTask9Tests(unittest.TestCase):
    def run_verifier(
        self, answer: str, navigated: bool = True, email: str = "alice.j@test.com"
    ):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--9",
                        "steps": [
                            {"url": "http://localhost:40016/login", "action": "input", "params": {"text": email}},
                            *([{"url": "http://localhost:40016/account/rewards"}] if navigated else []),
                        ],
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

    def test_correct_label_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "The newest reward activity is Bedroom storage order."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_rewards_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The newest reward activity is Bedroom storage order.", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_alice_rewards_page")

    def test_correct_answer_with_wrong_account_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The newest reward activity is Bedroom storage order.",
            email="bob.c@test.com",
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "entered_expected_account_email")

    def test_older_label_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The newest reward activity is Local planning appointment."
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
