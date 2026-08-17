from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_5.py"
SKUS = ("IK-10001", "IK-10002", "IK-11001")


def make_db(path: Path, carts: dict[str, dict[str, int]]) -> None:
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
                (1, 'bob.c@test.com'),
                (2, 'alice.j@test.com');
            INSERT INTO products(id, sku) VALUES
                (1, 'IK-10001'),
                (2, 'IK-10002'),
                (3, 'IK-11001');
            """
        )
        user_ids = {"bob.c@test.com": 1, "alice.j@test.com": 2}
        product_ids = {sku: index for index, sku in enumerate(SKUS, start=1)}
        for email, items in carts.items():
            for sku, quantity in items.items():
                if quantity:
                    connection.execute(
                        "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, ?, ?)",
                        (user_ids[email], product_ids[sku], quantity),
                    )
        connection.commit()
    finally:
        connection.close()


class VerifyTask5Tests(unittest.TestCase):
    def run_verifier(
        self,
        before: dict[str, dict[str, int]],
        after: dict[str, dict[str, int]],
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps({"task_id": "IKEA--5", "steps": [], "final_answer": ""}),
                encoding="utf-8",
            )
            before_db = root / "before.db"
            after_db = root / "after.db"
            make_db(before_db, before)
            make_db(after_db, after)
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
        returncode, verdict = self.run_verifier({}, {})
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_complete_bundle_passes(self) -> None:
        bundle = {sku: 1 for sku in SKUS}
        returncode, verdict = self.run_verifier({}, {"bob.c@test.com": bundle})
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_missing_bundle_item_fails(self) -> None:
        partial = {SKUS[0]: 1, SKUS[1]: 1}
        returncode, verdict = self.run_verifier({}, {"bob.c@test.com": partial})
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_wrong_account_bundle_fails(self) -> None:
        bundle = {sku: 1 for sku in SKUS}
        returncode, verdict = self.run_verifier({}, {"alice.j@test.com": bundle})
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_each_increment_is_relative_and_exact(self) -> None:
        before = {"bob.c@test.com": {sku: 2 for sku in SKUS}}
        after = {"bob.c@test.com": {sku: 3 for sku in SKUS}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
