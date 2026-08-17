from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_0.py"


def make_db(path: Path, wishlist_email: str | None = None) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);
            CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL);
            CREATE TABLE wishlist_items (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL
            );
            INSERT INTO users(id, email) VALUES
                (1, 'bob.c@test.com'),
                (2, 'alice.j@test.com');
            INSERT INTO products(id, sku) VALUES (1, 'IK-10001');
            """
        )
        if wishlist_email:
            user_id = 1 if wishlist_email == "bob.c@test.com" else 2
            connection.execute(
                "INSERT INTO wishlist_items(user_id, product_id) VALUES (?, 1)",
                (user_id,),
            )
        connection.commit()
    finally:
        connection.close()


class VerifyTask0Tests(unittest.TestCase):
    def run_verifier(
        self,
        before_owner: str | None,
        after_owner: str | None,
        use_run_snapshots: bool = False,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps({"task_id": "IKEA--0", "steps": [], "final_answer": ""}),
                encoding="utf-8",
            )
            before_db = (
                run_dir / "initial.db" if use_run_snapshots else root / "before.db"
            )
            after_db = (
                run_dir / "after.db" if use_run_snapshots else root / "after.db"
            )
            make_db(before_db, before_owner)
            make_db(after_db, after_owner)
            command = [sys.executable, str(VERIFIER), "--run_dir", str(run_dir)]
            if not use_run_snapshots:
                command.extend(
                    ["--initial_db", str(before_db), "--after_db", str(after_db)]
                )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
            )
            return result.returncode, json.loads(result.stdout)

    def test_reset_no_op_fails(self) -> None:
        returncode, verdict = self.run_verifier(None, None)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "target_saved_for_bob")

    def test_correct_bob_wishlist_change_passes(self) -> None:
        returncode, verdict = self.run_verifier(None, "bob.c@test.com")
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_standard_run_directory_snapshots_are_used_automatically(self) -> None:
        returncode, verdict = self.run_verifier(
            None, "bob.c@test.com", use_run_snapshots=True
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_wrong_account_change_fails(self) -> None:
        returncode, verdict = self.run_verifier(None, "alice.j@test.com")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_preexisting_target_fails_precondition(self) -> None:
        returncode, verdict = self.run_verifier(
            "bob.c@test.com", "bob.c@test.com"
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "initial_target_absent")


if __name__ == "__main__":
    unittest.main()
