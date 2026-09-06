"""Positive and adversarial tests for every Target verifier."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SEED_DB = VERIFY_DIR.parent / "instance_seed" / "target.db"
BASE = "http://localhost:40018"
PASSWORD = "TestPass123!"

SKUS = {
    1: "TGT91151386", 2: "TGT94764181", 4: "TGT91986267", 5: "TGT94760871",
    10: "TGT91151386", 11: "TGT94640332", 12: "TGT1012287965",
    17: "TGT85566854", 19: "TGT92595737",
}


def url(path: str) -> str:
    return BASE + path


def navigate(path: str) -> dict:
    return {"url": url(path), "action": "navigate", "params": {}}


def click(path: str, destination: str) -> dict:
    return {"url": url(path), "url_after": url(destination), "action": "click", "params": {}}


def enter(path: str, text: str, action: str = "input") -> dict:
    return {"url": url(path), "action": action, "params": {"text" if action != "select" else "option": text}}


def transition(source: str, destination: str) -> list[dict]:
    return [click(source, destination), navigate(destination)]


def login_steps(email: str) -> list[dict]:
    return [navigate("/login"), enter("/login", email), enter("/login", PASSWORD), click("/login", "/account"), navigate("/account")]


def next_id(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {table}").fetchone()[0]


class VerifierTests(unittest.TestCase):
    def run_verifier(self, task: int, steps: list[dict], answer: str, mutate=None, task_id: str | None = None) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory(prefix=f"target-verify-{task}-") as temp_dir:
            root = Path(temp_dir); initial = root / "initial.db"; after = root / "after.db"; run = root / "run"; run.mkdir()
            shutil.copy2(SEED_DB, initial); shutil.copy2(SEED_DB, after)
            if mutate:
                connection = sqlite3.connect(after)
                try:
                    mutate(connection); connection.commit()
                finally:
                    connection.close()
            trajectory = {"task_id": task_id or f"Target--{task}", "start_url": url("/"), "steps": steps, "final_url": steps[-1].get("url_after", steps[-1].get("url")) if steps else url("/"), "final_answer": answer}
            (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
            result = subprocess.run([sys.executable, str(VERIFY_DIR / f"verify_{task}.py"), "--run_dir", str(run), "--initial_db", str(initial), "--after_db", str(after), "--no_llm", "true"], capture_output=True, text=True, timeout=30, check=False)
            try: verdict = json.loads(result.stdout)
            except json.JSONDecodeError as error: self.fail(f"task {task} invalid output: {result.stdout!r} {result.stderr!r}: {error}")
            return result.returncode, verdict

    @staticmethod
    def mutate_cart(connection: sqlite3.Connection) -> None:
        uid = connection.execute("SELECT id FROM users WHERE email='carol.d@test.com'").fetchone()[0]
        pid = connection.execute("SELECT id FROM products WHERE sku='TGT91151386'").fetchone()[0]
        connection.execute("INSERT INTO cart_items(id,user_id,product_id,quantity,fulfillment_method,created_at) VALUES(?,?,?,?,?,?)", (next_id(connection, "cart_items"), uid, pid, 1, "delivery", "2026-04-01 10:00:00"))

    @staticmethod
    def _insert_order(connection: sqlite3.Connection, *, email: str, sku: str, quantity: int, fulfillment: str, street: str = "", city: str = "", state: str = "", zip_code: str = "", store_slug: str | None = None, slot_label: str = "") -> tuple[str, int, float]:
        uid = connection.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0]
        product_id, price = connection.execute("SELECT id,price FROM products WHERE sku=?", (sku,)).fetchone()
        order_id = next_id(connection, "orders"); number = f"TGT-TEST-{order_id}"; subtotal = round(price * quantity, 2); tax = round(subtotal * 0.086, 2); total = round(subtotal + tax, 2)
        store_id = connection.execute("SELECT id FROM stores WHERE slug=?", (store_slug,)).fetchone()[0] if store_slug else None
        delivery_id = connection.execute("SELECT id FROM delivery_options ORDER BY id LIMIT 1").fetchone()[0] if fulfillment == "delivery" else None
        connection.execute("INSERT INTO orders(id,user_id,order_number,email,status,subtotal,tax,total,fulfillment_method,store_id,delivery_option_id,shipping_name,shipping_street,shipping_city,shipping_state,shipping_zip,payment_brand,payment_last4,confirmation_note,pickup_slot_label,placed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (order_id, uid, number, email, "Processing" if fulfillment == "pickup" else "Preparing shipment", subtotal, tax, total, fulfillment, store_id, delivery_id, "Bob Chen", street, city, state, zip_code, "Demo Visa", "1111", "Demo", slot_label, "2026-04-01 10:00:00"))
        connection.execute("INSERT INTO order_items(id,order_id,product_id,item_name,quantity,unit_price,protection_plan_name) VALUES(?,?,?,?,?,?,?)", (next_id(connection, "order_items"), order_id, product_id, connection.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()[0], quantity, price, ""))
        connection.execute("INSERT INTO payment_mocks(id,order_id,amount,card_label,auth_status,approval_code,created_at) VALUES(?,?,?,?,?,?,?)", (next_id(connection, "payment_mocks"), order_id, total, "Demo Visa", "Approved", "TEST", "2026-04-01 10:00:00"))
        connection.execute("UPDATE reward_accounts SET points_balance=points_balance+? WHERE user_id=?", (int(subtotal), uid))
        connection.execute("INSERT INTO reward_activities(id,user_id,points_delta,title,note,created_at) VALUES(?,?,?,?,?,?)", (next_id(connection, "reward_activities"), uid, int(subtotal), f"Points from order {number}", "Demo", "2026-04-01 10:00:00"))
        return number, order_id, subtotal

    @classmethod
    def mutate_delivery_order(cls, connection: sqlite3.Connection) -> None:
        cls._insert_order(connection, email="bob.c@test.com", sku=SKUS[11], quantity=1, fulfillment="delivery", street="123 Main St", city="Denver", state="CO", zip_code="80202")

    @classmethod
    def mutate_pickup_order(cls, connection: sqlite3.Connection) -> None:
        number, _, _ = cls._insert_order(connection, email="bob.c@test.com", sku=SKUS[17], quantity=2, fulfillment="pickup", store_slug="denver-stapleton", slot_label="Tomorrow 9:00 AM - 11:00 AM")
        product_id = connection.execute("SELECT id FROM products WHERE sku=?", (SKUS[17],)).fetchone()[0]
        store_id = connection.execute("SELECT id FROM stores WHERE slug='denver-stapleton'").fetchone()[0]
        connection.execute("UPDATE store_inventory SET quantity=quantity-2 WHERE product_id=? AND store_id=?", (product_id, store_id))
        connection.execute("UPDATE pickup_slots SET available_capacity=available_capacity-1 WHERE store_id=? AND day_label='Tomorrow' AND time_window='9:00 AM - 11:00 AM'", (store_id,))

    @staticmethod
    def mutate_wishlist_add(connection: sqlite3.Connection) -> None:
        uid = connection.execute("SELECT id FROM users WHERE email='alice.j@test.com'").fetchone()[0]; pid = connection.execute("SELECT id FROM products WHERE sku=?", (SKUS[12],)).fetchone()[0]
        connection.execute("INSERT INTO wishlist_items(id,user_id,product_id,created_at) VALUES(?,?,?,?)", (next_id(connection, "wishlist_items"), uid, pid, "2026-04-01 10:00:00"))

    @staticmethod
    def mutate_wishlist_remove(connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM wishlist_items WHERE user_id=(SELECT id FROM users WHERE email='alice.j@test.com') AND product_id=(SELECT id FROM products WHERE sku='TGT12954143')")

    @staticmethod
    def mutate_ticket(connection: sqlite3.Connection) -> None:
        uid = connection.execute("SELECT id FROM users WHERE email='bob.c@test.com'").fetchone()[0]
        connection.execute("INSERT INTO support_tickets(id,user_id,subject,status,channel,summary,created_at) VALUES(?,?,?,?,?,?,?)", (next_id(connection, "support_tickets"), uid, "Order arrived damaged", "Open", "Email", "The package arrived with visible damage.", "2026-04-01 10:00:00"))

    @staticmethod
    def mutate_review(connection: sqlite3.Connection) -> None:
        pid, rating, count = connection.execute("SELECT id,rating,review_count FROM products WHERE sku=?", (SKUS[19],)).fetchone()
        connection.execute("INSERT INTO reviews(id,product_id,author_name,title,body,rating,verified,created_at) VALUES(?,?,?,?,?,?,?,?)", (next_id(connection, "reviews"), pid, "Carol Diaz", "Great sound for the size", "Clear sound and useful size for a small room.", 4, 0, "2026-04-01 10:00:00"))
        connection.execute("UPDATE products SET rating=?,review_count=? WHERE id=?", (round((rating * count + 4) / (count + 1), 1), count + 1, pid))

    def positive_case(self, task: int):
        product = lambda number: f"/product/{SKUS[number]}"
        red = "/search?q=Red+Baron"
        cases = {
            0: ([navigate("/support")] + transition("/support", "/support/returns-and-exchanges"), "Opened beauty items: 60 days. Target owned brands: one year.", None),
            1: ([navigate("/search?q=yoga+mat")] + transition("/search?q=yoga+mat", product(1)), "Nitrile Butadiene Rubber (NBR), 71 inches long.", None),
            2: ([navigate("/category/grocery")] + transition("/category/grocery", product(2)), "Sodium is 610 mg per serving.", None),
            3: ([navigate(red)] + transition(red, "/product/TGT13376389") + [navigate(red)] + transition(red, "/product/TGT13334000"), "Four Cheese has less sodium: 710 mg versus Pepperoni at 790 mg.", None),
            4: ([navigate("/search?q=Mr+Coffee")] + transition("/search?q=Mr+Coffee", product(4)), "74% would recommend it; Easy to Clean scored highest.", None),
            5: ([navigate("/category/electronics?brand=sony")] + transition("/category/electronics?brand=sony", product(5)), "The longer plan covers accidental handling and costs $22.95 more ($59.67 versus $36.72).", None),
            6: ([navigate("/category/pets?brand=boots-barkley&availability=pickup&deals=1&sort=price-asc")], "Cuddler Dog Bed - Blue - Boots & Barkley, $24.99.", None),
            7: ([navigate(red)] + transition(red, "/product/TGT13333997") + [click("/product/TGT13333997", "/product/TGT13333997"), navigate("/product/TGT13333997"), navigate(red)] + transition(red, "/product/TGT31168522") + [click("/product/TGT31168522", "/product/TGT31168522"), navigate("/product/TGT31168522"), navigate("/compare")], "Supreme has less sodium: 650 mg versus 810 mg, a 160 mg difference.", None),
            8: (login_steps("david.k@test.com") + transition("/account", "/account/orders"), "The Processing order is TGT-240013, total $32.61.", None),
            9: (login_steps("david.k@test.com") + transition("/account", "/account/rewards"), "The points balance is 2,185 points.", None),
            10: (login_steps("carol.d@test.com") + [navigate("/search?q=yoga+mat")] + transition("/search?q=yoga+mat", product(10)) + [click(product(10), product(10)), navigate(product(10))] + transition(product(10), "/cart"), "The cart subtotal is $408.96.", self.mutate_cart),
            11: (login_steps("bob.c@test.com") + [navigate("/search?q=Tide+Ultra+Oxi")] + transition("/search?q=Tide+Ultra+Oxi", product(11)) + [click(product(11), "/cart"), navigate("/cart"), navigate("/checkout/shipping"), enter("/checkout/shipping", "123 Main St"), enter("/checkout/shipping", "Denver"), enter("/checkout/shipping", "CO"), enter("/checkout/shipping", "80202"), click("/checkout/shipping", "/checkout/payment"), navigate("/checkout/payment"), click("/checkout/payment", "/checkout/review"), navigate("/checkout/review"), click("/checkout/review", "/checkout/confirmation"), navigate("/checkout/confirmation")], "Order TGT-TEST-17 was confirmed.", self.mutate_delivery_order),
            12: (login_steps("alice.j@test.com") + [navigate("/search?q=Colgate+Total+Whitening")] + transition("/search?q=Colgate+Total+Whitening", product(12)) + [click(product(12), product(12)), navigate(product(12)), navigate("/account/wishlist")], "The bottom item is Organic Mini Sandwich Cheddar Cheese Crackers.", self.mutate_wishlist_add),
            13: ([navigate("/stores")] + transition("/stores", "/stores/denver-stapleton"), "7400 E 29th Ave; Drive Up.", None),
            14: (login_steps("alice.j@test.com") + transition("/account", "/account/wishlist") + [click("/account/wishlist", "/account/wishlist"), navigate("/account/wishlist")], "Katie's Burrata Margherita; Cinnamon Toast Crunch; Organic Mini Sandwich Cheddar Cheese Crackers.", self.mutate_wishlist_remove),
            15: ([navigate(red)] + sum((transition(red, f"/product/{sku}") + [navigate(red)] for sku in ("TGT13333997", "TGT13334000", "TGT31168521", "TGT13376389", "TGT31168522")), []), "Red Baron Supreme Classic Crust has the lowest sodium at 650 mg per serving.", None),
            16: ([navigate("/search?q=Ninja+DualBrew")] + transition("/search?q=Ninja+DualBrew", "/product/TGT94682442") + [navigate("/search?q=Cuisinart+14+Cup")] + transition("/search?q=Cuisinart+14+Cup", "/product/TGT94139349"), "Ninja is higher at 66%; Cuisinart is 59%.", None),
            17: (login_steps("bob.c@test.com") + [navigate("/search?q=Colgate+Optic+White")] + transition("/search?q=Colgate+Optic+White", product(17)) + [enter(product(17), "2", "select"), click(product(17), "/cart"), navigate("/cart"), navigate("/checkout/pickup"), enter("/checkout/pickup", "Tomorrow 9:00 AM - 11:00 AM", "select"), click("/checkout/pickup", "/checkout/payment"), navigate("/checkout/payment"), click("/checkout/payment", "/checkout/review"), navigate("/checkout/review"), click("/checkout/review", "/checkout/confirmation"), navigate("/checkout/confirmation")], "Order TGT-TEST-17 was confirmed.", self.mutate_pickup_order),
            18: (login_steps("bob.c@test.com") + [navigate("/support")] + transition("/support", "/support/contact") + [enter("/support/contact", "Order arrived damaged"), enter("/support/contact", "The box arrived crushed and the product was damaged."), enter("/support/contact", "Email", "select"), click("/support/contact", "/account/support"), navigate("/account/support")], "The request status is Open.", self.mutate_ticket),
            19: (login_steps("carol.d@test.com") + [navigate("/search?q=Beats+Pill")] + transition("/search?q=Beats+Pill", product(19)) + [enter(product(19), "4", "select"), enter(product(19), "Great sound for the size"), enter(product(19), "Clear sound and useful size for a small room."), click(product(19), product(19)), navigate(product(19))], "The review 'Great sound for the size' appears on the product page.", self.mutate_review),
        }
        return cases[task]

    def test_all_positive_cases(self) -> None:
        for task in range(20):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task); code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict); self.assertTrue(verdict["pass"], verdict)

    def test_wrong_task_id_fails_all(self) -> None:
        for task in range(20):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task); code, verdict = self.run_verifier(task, steps, answer, mutate, "Target--999")
                self.assertNotEqual(0, code); self.assertEqual("task_id_matches", verdict["reason"])

    def test_answer_only_fails_all(self) -> None:
        for task in range(20):
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task); code, verdict = self.run_verifier(task, [], answer, mutate)
                self.assertNotEqual(0, code); self.assertFalse(verdict["pass"])

    def test_external_origin_and_url_only_fail(self) -> None:
        steps = [{"url": "https://attacker.invalid/?next=/product/TGT91151386", "action": "navigate", "params": {}}]
        code, verdict = self.run_verifier(1, steps, "NBR, 71 inches")
        self.assertNotEqual(0, code); self.assertFalse(verdict["pass"])

    def test_negated_answers_fail(self) -> None:
        cases = {
            2: "It is not 610 mg sodium; it is 450 mg.",
            4: "It is not 74%, and Easy to Clean did not score highest.",
            5: "The 3-year plan does not cover accidental handling; the gap is $22.95.",
            10: "The subtotal is not $408.96; it is $1.00.",
            15: "Supreme is not the answer, though its label says 650 mg.",
        }
        for task, answer in cases.items():
            with self.subTest(task=task):
                steps, _, mutate = self.positive_case(task); code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code); self.assertFalse(verdict["pass"])

    def test_state_tasks_reject_unrelated_changes(self) -> None:
        for task in (10, 11, 12, 14, 17, 18, 19):
            with self.subTest(task=task):
                steps, answer, base_mutate = self.positive_case(task)
                def mutate(connection, base_mutate=base_mutate):
                    base_mutate(connection); connection.execute("UPDATE users SET city='Unrelated mutation' WHERE email='david.k@test.com'")
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code); self.assertFalse(verdict["pass"])

    def test_natural_equivalents_pass(self) -> None:
        steps, _, _ = self.positive_case(5); code, verdict = self.run_verifier(5, steps, "The longer plan includes accidental handling; prices are $59.67 and $36.72.")
        self.assertEqual(0, code, verdict)
        steps, _, _ = self.positive_case(13); code, verdict = self.run_verifier(13, steps, "The address is 7400 E 29th Ave and it offers Order Pickup.")
        self.assertEqual(0, code, verdict)

    def test_checkout_rejects_wrong_address_and_wrong_store(self) -> None:
        steps, answer, _ = self.positive_case(11)
        def wrong_address(connection): self._insert_order(connection, email="bob.c@test.com", sku=SKUS[11], quantity=1, fulfillment="delivery", street="999 Wrong Rd", city="Boston", state="MA", zip_code="02108")
        code, verdict = self.run_verifier(11, steps, answer, wrong_address); self.assertNotEqual(0, code); self.assertFalse(verdict["pass"])
        steps, answer, _ = self.positive_case(17)
        def wrong_store(connection): self._insert_order(connection, email="bob.c@test.com", sku=SKUS[17], quantity=2, fulfillment="pickup", store_slug="austin-domain", slot_label="Tomorrow 9:00 AM - 11:00 AM")
        code, verdict = self.run_verifier(17, steps, answer, wrong_store); self.assertNotEqual(0, code); self.assertFalse(verdict["pass"])


if __name__ == "__main__": unittest.main()
