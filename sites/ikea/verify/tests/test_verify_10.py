from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_10.py"
PRODUCTS = {"IK-SAVED": 1, "IK-OTHER": 2}


def make_db(
    path: Path,
    bob_wishlist: set[str],
    bob_cart: dict[str, int],
    alice_cart: dict[str, int] | None = None,
) -> None:
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
                (1, 'IK-SAVED'),
                (2, 'IK-OTHER');
            """
        )
        for sku in bob_wishlist:
            connection.execute(
                "INSERT INTO wishlist_items(user_id, product_id) VALUES (1, ?)",
                (PRODUCTS[sku],),
            )
        for user_id, cart in ((1, bob_cart), (2, alice_cart or {})):
            for sku, quantity in cart.items():
                connection.execute(
                    "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, ?, ?)",
                    (user_id, PRODUCTS[sku], quantity),
                )
        connection.commit()
    finally:
        connection.close()


class VerifyTask10Tests(unittest.TestCase):
    def run_verifier(self, before: dict, after: dict, valid_trajectory: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--10",
                        "steps": ([
                            {"url": "http://localhost:40016/login", "action": "input", "params": {"text": "bob.c@test.com"}},
                            {"url": "http://localhost:40016/account/wishlist"},
                            {"url": "http://localhost:40016/product/IK-SAVED"},
                            {"url": "http://localhost:40016/cart"},
                        ] if valid_trajectory else []),
                        "final_answer": ("Added one saved item to the cart and kept it saved." if valid_trajectory else ""),
                    }
                ),
                encoding="utf-8",
            )
            before_db = root / "before.db"
            after_db = root / "after.db"
            make_db(before_db, **before)
            make_db(after_db, **after)
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
        state = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {}}
        returncode, verdict = self.run_verifier(state, state)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_saved_item_added_and_kept_passes(self) -> None:
        before = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {}}
        after = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {"IK-SAVED": 1}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_state_change_without_browser_flow_fails(self) -> None:
        before = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {}}
        after = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {"IK-SAVED": 1}}
        returncode, verdict = self.run_verifier(before, after, valid_trajectory=False)
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "final_answer_nonempty")

    def test_removed_from_wishlist_after_add_fails(self) -> None:
        before = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {}}
        after = {"bob_wishlist": set(), "bob_cart": {"IK-SAVED": 1}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_non_wishlist_item_add_fails(self) -> None:
        before = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {}}
        after = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {"IK-OTHER": 1}}
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_wrong_account_add_fails(self) -> None:
        before = {"bob_wishlist": {"IK-SAVED"}, "bob_cart": {}}
        after = {
            "bob_wishlist": {"IK-SAVED"},
            "bob_cart": {},
            "alice_cart": {"IK-SAVED": 1},
        }
        returncode, verdict = self.run_verifier(before, after)
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
