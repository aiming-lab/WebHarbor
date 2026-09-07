from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_13.py"


class VerifyTask13Tests(unittest.TestCase):
    def run_verifier(self, answer: str, navigated: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--13",
                        "steps": ([{"url": "http://localhost:40016/stores/atlanta-ga"}] if navigated else []),
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

    def test_each_atlanta_service_passes(self) -> None:
        for service in ("Assembly planning", "Kitchen consultation", "Returns desk"):
            with self.subTest(service=service):
                returncode, verdict = self.run_verifier(
                    f"One listed service is {service}."
                )
                self.assertEqual(returncode, 0)
                self.assertTrue(verdict["pass"])

    def test_correct_answer_without_store_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "One listed service is Assembly planning.", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_atlanta_store_page")

    def test_amenity_is_not_a_service_fails(self) -> None:
        returncode, verdict = self.run_verifier("Swedish Restaurant")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_unlisted_service_fails(self) -> None:
        returncode, verdict = self.run_verifier("Large item loading")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
