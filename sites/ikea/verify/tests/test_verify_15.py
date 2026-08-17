from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_15.py"


def make_db(path: Path, compare_owner: str | None = None) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);
            CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL);
            CREATE TABLE compare_items (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL
            );
            INSERT INTO users(id, email) VALUES
                (1, 'alice.j@test.com'),
                (2, 'bob.c@test.com');
            INSERT INTO products(id, sku) VALUES (1, 'IK-10010');
            """
        )
        if compare_owner:
            user_id = 1 if compare_owner == "alice.j@test.com" else 2
            connection.execute(
                "INSERT INTO compare_items(user_id, product_id) VALUES (?, 1)",
                (user_id,),
            )
        connection.commit()
    finally:
        connection.close()


class VerifyTask15Tests(unittest.TestCase):
    def run_verifier(
        self,
        answer: str,
        before_owner: str | None = None,
        after_owner: str | None = None,
        navigated: bool = True,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--15",
                        "steps": ([{"url": "http://localhost:40016/compare"}] if navigated else []),
                        "final_answer": answer,
                    }
                ),
                encoding="utf-8",
            )
            before_db = root / "before.db"
            after_db = root / "after.db"
            make_db(before_db, before_owner)
            make_db(after_db, after_owner)
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--run_dir",
                    str(run_dir),
                    "--initial_db",
                    str(before_db),
                    "--after_db",
                    str(after_db),
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode, json.loads(result.stdout)

    def test_reset_no_op_fails(self) -> None:
        returncode, verdict = self.run_verifier("")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_correct_state_and_full_spec_pass(self) -> None:
        returncode, verdict = self.run_verifier(
            "One displayed row is IKEA product ID: 00311498.",
            after_owner="alice.j@test.com",
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_state_without_answer_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "", after_owner="alice.j@test.com"
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "answer_has_complete_spec_row")

    def test_correct_state_and_answer_without_compare_navigation_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "Size: 14\"", after_owner="alice.j@test.com", navigated=False
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_compare_page")

    def test_answer_without_state_fails(self) -> None:
        returncode, verdict = self.run_verifier("Size: 14\"")
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "target_added_to_alice_compare")

    def test_wrong_account_state_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "Availability: Ready for pickup", after_owner="bob.c@test.com"
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_value_without_spec_name_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            'It is 14".', after_owner="alice.j@test.com"
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
