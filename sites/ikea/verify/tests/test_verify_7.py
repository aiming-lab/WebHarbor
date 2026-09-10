from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_7.py"


class VerifyTask7Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--7",
                        "steps": ([{"url": "http://localhost:40016/support/large-item-delivery"}] if navigated else []),
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

    def test_exact_label_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "It explains Room-of-choice delivery."
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_correct_answer_without_article_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "It explains Room-of-choice delivery.", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_large_item_delivery_article")

    def test_space_variant_passes(self) -> None:
        returncode, verdict = self.run_verifier("ROOM OF CHOICE DELIVERY")
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_wrong_delivery_type_fails(self) -> None:
        returncode, verdict = self.run_verifier("It explains truck delivery.")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
