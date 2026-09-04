from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
VERIFIER = VERIFY_DIR / "verify_17.py"
INITIAL_CART = {"IK-A": 1, "IK-B": 2}
INITIAL_ORDERS = {"IK-240001", "IK-240005"}


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


class VerifyTask17Tests(unittest.TestCase):
    def run_verifier(
        self, answer: str, after_cart=None, after_orders=None, valid_trajectory: bool = True
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "task_id": "IKEA--17",
                        "steps": ([
                            {"url": "http://localhost:40016/login", "action": "input", "params": {"text": "alice.j@test.com"}},
                            {"url": "http://localhost:40016/cart"},
                            {"url": "http://localhost:40016/checkout"},
                            {"url": "http://localhost:40016/checkout/payment"},
                            {"url": "http://localhost:40016/checkout/review"},
                            {"url": "http://localhost:40016/checkout/confirmation"},
                        ] if valid_trajectory else []),
                        "final_answer": answer,
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

    def test_reset_no_op_fails(self) -> None:
        returncode, verdict = self.run_verifier("")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])

    def test_exactly_one_order_cart_clear_and_matching_answer_passes(self) -> None:
        new_order = "IK-260061"
        returncode, verdict = self.run_verifier(
            f"The confirmation order number is {new_order}.",
            after_cart={},
            after_orders=INITIAL_ORDERS | {new_order},
        )
        self.assertEqual(returncode, 0)
        self.assertTrue(verdict["pass"])

    def test_state_change_without_browser_flow_fails(self) -> None:
        new_order = "IK-260061"
        returncode, verdict = self.run_verifier(
            new_order,
            after_cart={},
            after_orders=INITIAL_ORDERS | {new_order},
            valid_trajectory=False,
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "visited_login_page")

    def test_wrong_reported_order_number_fails(self) -> None:
        returncode, verdict = self.run_verifier(
            "The confirmation number is IK-260062.",
            after_cart={},
            after_orders=INITIAL_ORDERS | {"IK-260061"},
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "answer_matches_new_order_number")

    def test_two_new_orders_fail(self) -> None:
        new_orders = {"IK-260061", "IK-260062"}
        returncode, verdict = self.run_verifier(
            "IK-260061", after_cart={}, after_orders=INITIAL_ORDERS | new_orders
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "alice_added_exactly_one_order")

    def test_cart_not_cleared_fails(self) -> None:
        new_order = "IK-260061"
        returncode, verdict = self.run_verifier(
            new_order,
            after_cart={"IK-A": 1},
            after_orders=INITIAL_ORDERS | {new_order},
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(verdict["reason"], "alice_cart_cleared")

    def test_answer_only_claim_fails(self) -> None:
        returncode, verdict = self.run_verifier("IK-260061")
        self.assertEqual(returncode, 1)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
