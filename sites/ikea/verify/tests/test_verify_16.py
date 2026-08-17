from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_16.py"
INITIAL_CART = {"IK-A": 1, "IK-B": 2}
INITIAL_ORDERS = {"IK-OLD-1", "IK-OLD-2"}


def make_db(path: Path, cart: dict[str, int], orders: set[str]) -> None:
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
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                order_number TEXT NOT NULL
            );
            INSERT INTO users(id, email) VALUES (1, 'alice.j@test.com');
            INSERT INTO products(id, sku) VALUES (1, 'IK-A'), (2, 'IK-B');
            """
        )
        product_ids = {"IK-A": 1, "IK-B": 2}
        for sku, quantity in cart.items():
            connection.execute(
                "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (1, ?, ?)",
                (product_ids[sku], quantity),
            )
        for order_number in sorted(orders):
            connection.execute(
                "INSERT INTO orders(user_id, order_number) VALUES (1, ?)",
                (order_number,),
            )
        connection.commit()
    finally:
        connection.close()


class VerifyTask16Tests(unittest.TestCase):
    def run_verifier(self, url: str, after_cart=None, after_orders=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--16",
                        "steps": [{"url": url, "action": "done"}],
                        "final_answer": "",
                    }
                ),
                encoding="utf-8",
            )
            before_db = root / "before.db"
            after_db = root / "after.db"
            make_db(before_db, INITIAL_CART, INITIAL_ORDERS)
            make_db(
                after_db,
                INITIAL_CART if after_cart is None else after_cart,
                INITIAL_ORDERS if after_orders is None else after_orders,
            )
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

    def test_reset_homepage_no_op_fails(self) -> None:
        returncode, verdict = self.run_verifier("http://localhost:40016/")
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "final_url_is_checkout_review")

    def test_review_with_unchanged_state_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "http://localhost:40016/checkout/review?from=payment"
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_done_step_review_url_passes(self) -> None:
        returncode, verdict = self.run_verifier(
            "http://localhost:40016/checkout/review"
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_placed_order_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "http://localhost:40016/checkout/review",
            after_cart={},
            after_orders=INITIAL_ORDERS | {"IK-NEW"},
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_cart_change_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "http://localhost:40016/checkout/review",
            after_cart={"IK-A": 2, "IK-B": 2},
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "alice_cart_unchanged")

    def test_confirmation_url_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "http://localhost:40016/checkout/confirmation/IK-NEW"
        )
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
