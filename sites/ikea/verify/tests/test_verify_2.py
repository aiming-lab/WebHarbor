from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_2.py"


def make_db(path: Path, users: dict[str, set[str]]) -> None:
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
            INSERT INTO products(id, sku) VALUES
                (1, 'IK-10005'),
                (2, 'IK-10006');
            """
        )
        for user_id, (email, skus) in enumerate(users.items(), start=1):
            connection.execute(
                "INSERT INTO users(id, email) VALUES (?, ?)", (user_id, email)
            )
            for sku in skus:
                product_id = 1 if sku == "IK-10005" else 2
                connection.execute(
                    "INSERT INTO compare_items(user_id, product_id) VALUES (?, ?)",
                    (user_id, product_id),
                )
        connection.commit()
    finally:
        connection.close()


class VerifyTask2Tests(unittest.TestCase):
    def run_verifier(
        self, before_users: dict[str, set[str]], after_users: dict[str, set[str]]
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps({"task_id": "IKEA--2", "steps": [], "final_answer": ""}),
                encoding="utf-8",
            )
            before_db = root / "before.db"
            after_db = root / "after.db"
            make_db(before_db, before_users)
            make_db(after_db, after_users)
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
        users = {"alice.j@test.com": {"IK-10005", "IK-10006"}}
        returncode, verdict = self.run_verifier(users, users)
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "new_user_registered")

    def test_new_user_with_both_targets_passes(self) -> None:
        before = {"alice.j@test.com": set()}
        after = {
            **before,
            "new.user@example.com": {"IK-10005", "IK-10006"},
        }
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_new_user_with_incomplete_compare_fails(self) -> None:
        before = {"alice.j@test.com": set()}
        after = {**before, "new.user@example.com": {"IK-10005"}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "new_user_compared_both_targets")

    def test_existing_user_cannot_satisfy_new_user_requirement(self) -> None:
        before = {"alice.j@test.com": set()}
        after = {"alice.j@test.com": {"IK-10005", "IK-10006"}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_renaming_existing_user_is_not_registration(self) -> None:
        before = {"alice.j@test.com": set()}
        after = {"renamed.alice@example.com": {"IK-10005", "IK-10006"}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "new_user_registered")

    def test_any_one_of_multiple_new_users_may_complete(self) -> None:
        before = {"alice.j@test.com": set()}
        after = {
            **before,
            "partial@example.com": {"IK-10005"},
            "complete@example.com": {"IK-10005", "IK-10006"},
        }
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
