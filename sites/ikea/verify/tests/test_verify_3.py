from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_3.py"


def make_db(path: Path, alice_quantity: int = 0, bob_quantity: int = 0) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);
            CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL);
            CREATE TABLE cart_items (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL
            );
            INSERT INTO users(id, email) VALUES
                (1, 'alice.j@test.com'),
                (2, 'bob.c@test.com');
            INSERT INTO products(id, sku) VALUES (1, 'IK-10007');
            """
        )
        for user_id, quantity in ((1, alice_quantity), (2, bob_quantity)):
            if quantity:
                connection.execute(
                    "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, 1, ?)",
                    (user_id, quantity),
                )
        connection.commit()
    finally:
        connection.close()


class VerifyTask3Tests(unittest.TestCase):
    def run_verifier(
        self,
        before_alice: int = 0,
        after_alice: int = 0,
        after_bob: int = 0,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps({"task_id": "IKEA--3", "steps": [], "final_answer": ""}),
                encoding="utf-8",
            )
            before_db = root / "before.db"
            after_db = root / "after.db"
            make_db(before_db, alice_quantity=before_alice)
            make_db(after_db, alice_quantity=after_alice, bob_quantity=after_bob)
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
        returncode, verdict = self.run_verifier()
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_exactly_one_added_passes(self) -> None:
        returncode, verdict = self.run_verifier(after_alice=1)
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_two_added_fails(self) -> None:
        returncode, verdict = self.run_verifier(after_alice=2)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_wrong_account_added_fails(self) -> None:
        returncode, verdict = self.run_verifier(after_bob=1)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_increment_is_relative_to_initial(self) -> None:
        returncode, verdict = self.run_verifier(before_alice=2, after_alice=3)
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
