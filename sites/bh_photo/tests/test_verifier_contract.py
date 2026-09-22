"""Regression cases from the task audit; no API key or live database needed."""

import importlib.util
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "bh_verifier_helpers", Path(__file__).resolve().parents[1] / "verify/verify_lib.py"
)
helpers = importlib.util.module_from_spec(spec)
import sys

sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


class AnswerContractTests(unittest.TestCase):
    def test_quantity_units_and_equivalent_scales(self):
        cases = [
            ("The angle is 220°.", 220, {r"°|degrees?": 1}, True),
            ("The angle is not 220 degrees; it is 180 degrees.", 220, {r"°|degrees?": 1}, False),
            ("220 radians", 220, {r"°|degrees?": 1}, False),
            ("Resolution: 1.04 million dots", 1040000, {r"dots?": 1}, True),
            ("1,040 dots", 1040000, {r"dots?": 1}, False),
            ("Max read: 1.8 GB/s", 1800, {r"mb/s": 1, r"gb/s": 1000, r"kb/s": .001}, True),
            ("Max read: 1800 KB/s", 1800, {r"mb/s": 1, r"gb/s": 1000, r"kb/s": .001}, False),
            ("4.06 kg", 4.06, {r"lb|pounds?": 1}, False),
        ]
        for text, value, units, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(helpers.states_measurement(text, value, units), expected)

    def test_count_is_not_an_aperture_or_a_negated_count(self):
        for text in ("2 matching products", "Two results", "The result count is 2."):
            self.assertTrue(helpers.states_count(text, 2, ["products", "results"]))
        for text in ("Not 2 matching products; there are 3 products.", "TTArtisan f/2 Lens"):
            self.assertFalse(helpers.states_count(text, 2, ["products", "results"]))

    def test_money_is_not_a_reference_number(self):
        self.assertTrue(helpers.states_price("The kit costs $12,775.03.", 12775.03))
        self.assertFalse(helpers.states_price("The kit costs $1. Reference number 12775.03.", 12775.03))

    def test_capacity_spacing_does_not_change_product_identity(self):
        product = "SanDisk 512GB Extreme PRO CFexpress Type B Memory Card with 128GB Extreme PRO UHS-II SDXC Memory Card"
        self.assertTrue(helpers.names_product(product.replace("512GB", "512 GB").replace("128GB", "128 GB"), product))
        self.assertFalse(helpers.names_product(product.replace("128GB", "64GB"), product))

    def test_pickup_policy_requires_the_condition_and_correct_polarity(self):
        self.assertTrue(helpers.states_pickup_policy("Store pickup is offered wherever this page shows counter stock."))
        self.assertTrue(helpers.states_pickup_policy("You can collect it at the shop if the displayed local inventory is available."))
        self.assertFalse(helpers.states_pickup_policy("Pickup is never offered, regardless of the stock at the counter."))
        self.assertFalse(helpers.states_pickup_policy("Pickup is offered at the counter."))

    def test_order_number_must_be_affirmed(self):
        self.assertTrue(helpers.affirmative_contains("BH-20260412-0201 is Processing.", "BH-20260412-0201"))
        self.assertFalse(helpers.affirmative_contains("It is not BH-20260412-0201; it is BH-99999999-0000.", "BH-20260412-0201"))

    def test_empty_compare_is_not_three_products(self):
        trajectory = {"start_url": "http://localhost:40030/", "steps": [{"url": "http://localhost:40030/compare"}]}
        self.assertFalse(helpers.compare_members_seen(trajectory, ["apple", "lenovo", "asus"], "", ""))


class StateDeltaContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.initial = str(Path(self.temp.name) / "initial.db")
        self.after = str(Path(self.temp.name) / "after.db")
        with sqlite3.connect(self.initial) as db:
            db.execute("CREATE TABLE cart_items(id INTEGER PRIMARY KEY, user_id INTEGER, product_id INTEGER, quantity INTEGER)")
            db.execute("INSERT INTO cart_items VALUES(1, 1, 10, 2), (2, 2, 20, 1)")
        shutil.copy2(self.initial, self.after)

    def mutate(self, sql):
        with sqlite3.connect(self.after) as db:
            db.execute(sql)

    def test_extra_item_and_other_users_are_not_allowed(self):
        wanted = {"user_id": 1, "product_id": 30, "quantity": 2}
        self.mutate("INSERT INTO cart_items VALUES(3, 1, 30, 2)")
        self.assertTrue(helpers.exact_addition(self.initial, self.after, "cart_items", wanted))
        self.mutate("INSERT INTO cart_items VALUES(4, 1, 40, 1)")
        self.assertFalse(helpers.exact_addition(self.initial, self.after, "cart_items", wanted))
        self.mutate("DELETE FROM cart_items WHERE id=4")
        self.mutate("DELETE FROM cart_items WHERE user_id=2")
        self.assertFalse(helpers.exact_addition(self.initial, self.after, "cart_items", wanted))

    def test_surviving_quantity_must_not_change(self):
        self.mutate("DELETE FROM cart_items WHERE id=2")
        self.assertTrue(helpers.rows_unchanged_except(self.initial, self.after, "cart_items", [2]))
        self.mutate("UPDATE cart_items SET quantity=3 WHERE id=1")
        self.assertFalse(helpers.rows_unchanged_except(self.initial, self.after, "cart_items", [2]))

    def test_cart_total_uses_quantity_and_tax(self):
        self.assertEqual(helpers.cart_totals([{"price": 280.08, "quantity": 2}])["total"], 609.87)
        self.assertNotEqual(helpers.cart_totals([{"price": 280.08, "quantity": 3}])["total"], 609.87)


if __name__ == "__main__":
    unittest.main()
