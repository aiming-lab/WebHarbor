"""Failure-path contract tests in an isolated copy of the Best Buy app."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest


class FunctionalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = Path(__file__).resolve().parents[1]
        cls.scratch = tempfile.TemporaryDirectory(prefix="bestbuy-contract-")
        cls.addClassCleanup(cls.scratch.cleanup)
        root = Path(cls.scratch.name)
        shutil.copy2(source / "app.py", root / "app.py")
        shutil.copytree(source / "templates", root / "templates")

        seed_stub = types.ModuleType("seed_data")
        seed_stub.ensure_seed_data = lambda *args, **kwargs: None
        previous = sys.modules.get("seed_data")
        sys.modules["seed_data"] = seed_stub
        try:
            spec = importlib.util.spec_from_file_location("_bestbuy_contract_app", root / "app.py")
            cls.site = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.site
            spec.loader.exec_module(cls.site)
        finally:
            if previous is None:
                sys.modules.pop("seed_data", None)
            else:
                sys.modules["seed_data"] = previous
        cls.addClassCleanup(sys.modules.pop, "_bestbuy_contract_app", None)
        cls.app = cls.site.app
        cls.db = cls.site.db
        cls.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    @classmethod
    def tearDownClass(cls) -> None:
        with cls.app.app_context():
            cls.db.session.remove()
            cls.db.engine.dispose()
        super().tearDownClass()

    def setUp(self) -> None:
        with self.app.app_context():
            self.db.drop_all()
            self.db.create_all()
            brand = self.site.Brand(name="Fixture", slug="fixture")
            category = self.site.Category(name="Fixture", slug="fixture")
            self.db.session.add_all([brand, category])
            self.db.session.flush()
            self.product = self.site.Product(
                sku="1000001", slug="fixture-one", name="Fixture One", price=10,
                list_price=10, category_id=category.id, brand_id=brand.id,
            )
            self.other_product = self.site.Product(
                sku="1000002", slug="fixture-two", name="Fixture Two", price=20,
                list_price=20, category_id=category.id, brand_id=brand.id,
            )
            self.store = self.site.Store(
                slug="fixture-store", name="Fixture Store", city="Seattle", state="WA",
                address="1 Test Way",
            )
            self.other_store = self.site.Store(
                slug="other-store", name="Other Store", city="Austin", state="TX",
                address="2 Test Way",
            )
            self.delivery = self.site.DeliveryOption(
                slug="standard", title="Standard", fee=0, eta_label="Soon",
            )
            user = self.site.User(email="alice@example.com", full_name="Alice Fixture")
            user.set_password(self.site.BENCHMARK_PASSWORD)
            self.db.session.add_all([
                self.product, self.other_product, self.store, self.other_store,
                self.delivery, user,
            ])
            self.db.session.flush()
            self.slot = self.site.PickupSlot(
                store_id=self.store.id, slot_code="fixture-slot", day_label="Tomorrow",
                time_window="10:00 AM - 12:00 PM", available_capacity=2,
            )
            self.foreign_plan = self.site.ProtectionPlan(
                product_id=self.other_product.id, name="Other Product Plan", years=2,
                price=5,
            )
            self.db.session.add_all([self.slot, self.foreign_plan])
            self.db.session.commit()
            self.ids = {
                "product": self.product.id,
                "other_product": self.other_product.id,
                "store": self.store.id,
                "other_store": self.other_store.id,
                "delivery": self.delivery.id,
                "slot": self.slot.id,
                "foreign_plan": self.foreign_plan.id,
            }

    def csrf(self, client) -> str:
        with client.session_transaction() as session:
            existing = session.get("bestbuy_csrf_token")
        if existing:
            return existing
        body = client.get("/login").get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', body)
        self.assertIsNotNone(match, "GET form must issue a CSRF token")
        return match.group(1)

    def post(self, client, path, data=None, **kwargs):
        return client.post(path, data={"csrf_token": self.csrf(client), **(data or {})}, **kwargs)

    def login(self, next_url=None):
        client = self.app.test_client()
        path = "/login" + (f"?next={next_url}" if next_url else "")
        response = self.post(client, path, {
            "email": "alice@example.com", "password": self.site.BENCHMARK_PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        return client, response

    def add_cart_fixture(self, client) -> None:
        response = self.post(client, "/cart/add", {
            "sku": "1000001", "quantity": "1", "fulfillment_method": "delivery",
            "delivery_option_id": str(self.ids["delivery"]),
        })
        self.assertEqual(response.status_code, 302)

    def state_counts(self):
        with self.app.app_context():
            return {
                "cart": self.site.CartItem.query.count(),
                "orders": self.site.Order.query.count(),
            }

    def test_post_requires_csrf_and_logout_is_not_get(self) -> None:
        client = self.app.test_client()
        response = client.post("/login", data={"email": "alice@example.com", "password": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(client.get("/logout").status_code, 405)

    def test_login_rejects_external_next_target(self) -> None:
        _, response = self.login("https://example.com/steal")
        self.assertEqual(response.location, "/account")

    def test_product_search_matches_separated_terms_and_sku(self) -> None:
        client = self.app.test_client()
        response = client.get("/search?q=Fixture+1000001")
        self.assertEqual(response.status_code, 200)
        self.assertIn('/product/1000001', response.get_data(as_text=True))

    def test_bad_quantity_and_foreign_plan_are_atomic(self) -> None:
        client, _ = self.login()
        before = self.state_counts()
        bad_quantity = self.post(client, "/cart/add", {
            "sku": "1000001", "quantity": "abc", "fulfillment_method": "delivery",
            "delivery_option_id": str(self.ids["delivery"]),
        })
        self.assertEqual(bad_quantity.status_code, 400)
        self.assertEqual(self.state_counts(), before)
        foreign_plan = self.post(client, "/cart/add", {
            "sku": "1000001", "quantity": "1", "fulfillment_method": "delivery",
            "delivery_option_id": str(self.ids["delivery"]),
            "protection_plan_id": str(self.ids["foreign_plan"]),
        })
        self.assertEqual(foreign_plan.status_code, 400)
        self.assertEqual(self.state_counts(), before)

    def test_checkout_rejects_invalid_delivery_pickup_and_payment_without_state_change(self) -> None:
        client, _ = self.login()
        self.add_cart_fixture(client)
        with client.session_transaction() as session:
            before = dict(session.get("bestbuy_checkout", {}))

        bad_shipping = self.post(client, "/checkout/shipping", {
            "delivery_option_id": "999999", "shipping_name": "",
            "shipping_city": "Seattle", "shipping_state": "WA", "shipping_zip": "bad",
        })
        self.assertEqual(bad_shipping.status_code, 400)
        with client.session_transaction() as session:
            self.assertEqual(session.get("bestbuy_checkout", {}), before)

        bad_pickup = self.post(client, "/checkout/pickup", {
            "store_id": str(self.ids["other_store"]), "slot_id": str(self.ids["slot"]),
        })
        self.assertEqual(bad_pickup.status_code, 400)
        with client.session_transaction() as session:
            self.assertEqual(session.get("bestbuy_checkout", {}), before)

        bad_payment = self.post(client, "/checkout/payment", {
            "payment_brand": "Demo Visa", "payment_last4": "abcd",
        })
        self.assertEqual(bad_payment.status_code, 400)
        with client.session_transaction() as session:
            self.assertEqual(session.get("bestbuy_checkout", {}), before)

    def test_checkout_task_inputs_are_not_prefilled(self) -> None:
        client, _ = self.login()
        self.add_cart_fixture(client)

        shipping = client.get("/checkout/shipping").get_data(as_text=True)
        for field in ("shipping_name", "shipping_city", "shipping_state", "shipping_zip"):
            self.assertRegex(shipping, rf'name="{field}" value=""')
        self.assertIn('<option value="" disabled selected>Select a delivery option</option>', shipping)

        pickup = client.get("/checkout/pickup").get_data(as_text=True)
        self.assertIn('<option value="" disabled selected>Select a store</option>', pickup)
        self.assertIn('<option value="" disabled selected>Select a pickup slot</option>', pickup)

        payment = client.get("/checkout/payment").get_data(as_text=True)
        self.assertIn('<option value="" disabled selected>Select a payment label</option>', payment)
        self.assertRegex(payment, r'name="payment_last4" maxlength="4" value=""')
        for label in self.site.PAYMENT_BRANDS:
            self.assertIn(f'<option value="{label}"', payment)

    def test_review_revalidates_forged_checkout_state(self) -> None:
        client, _ = self.login()
        self.add_cart_fixture(client)
        with client.session_transaction() as session:
            session["bestbuy_checkout"] = {
                "mode": "pickup", "store_id": str(self.ids["other_store"]),
                "slot_id": str(self.ids["slot"]), "payment_brand": "Demo Visa",
                "payment_last4": "1111",
            }
        before = self.state_counts()
        response = self.post(client, "/checkout/review")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/checkout/pickup")
        self.assertEqual(self.state_counts(), before)


if __name__ == "__main__":
    unittest.main()
