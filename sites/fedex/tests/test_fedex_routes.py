from __future__ import annotations

import os
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_ROOT))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402
from app import PickupRequest, User, app, db  # noqa: E402
from seed_data import seed_benchmark_users, seed_database  # noqa: E402

# Tests drive the site's canonical instance database, the convention the other
# sites follow. No FEDEX_DATABASE_URI is exported, because `app` reads that
# variable at import time and a value set here would leak into any subprocess a
# later test module starts.
TEST_DB_PATH = site.DB_PATH


class FedExRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    @classmethod
    def tearDownClass(cls) -> None:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        TEST_DB_PATH.unlink(missing_ok=True)

    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_homepage_has_real_tools_and_no_prefilled_task_answers(self) -> None:
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)
        for label in (b"RATE &amp; SHIP", b"TRACK", b"LOCATIONS", b"Why ship with FedEx?",
                      b"Delivery that works around you", b"Smarter shipping for growing businesses"):
            self.assertIn(label.lower(), response.data.lower())
        for leaked_value in (b"TestPass123!", b"alice.j@test.com", b"FDX260000004", b"demo workflow"):
            self.assertNotIn(leaked_value, response.data)
        self.assertIn(b'aria-label="Sign Up or Log In"', response.data)
        self.assertRegex(
            response.data,
            rb'<link rel="icon"[^>]+href="/static/external_cache/fedex-home/logo\.png"',
        )

    def test_register_rejects_invalid_email_or_missing_required_values(self) -> None:
        baseline = User.query.count()
        valid = {"email": "new-user@example.test", "password": "TestPass123!",
                 "first_name": "New", "last_name": "User"}
        for invalid in ({"email": "invalid-email"}, {"email": "a@b"},
                        {"password": ""}, {"first_name": "   "}, {"last_name": ""}):
            with self.subTest(invalid=invalid):
                self.client = app.test_client()
                response = self.client.post("/register", data={**valid, **invalid})
                self.assertEqual(400, response.status_code)
                self.assertTrue(
                    b"Enter a valid email address." in response.data
                    or b"Enter a first name" in response.data
                    or b"Enter a last name" in response.data
                    or b"Enter a password between" in response.data,
                    response.data[:400])
                self.assertEqual(baseline, User.query.count())

    def test_registered_account_can_sign_in_with_normalized_email(self) -> None:
        response = self.client.post("/register", data={
            "email": " New-User@Example.Test ", "password": "TestPass123!",
            "first_name": "New", "last_name": "User",
        })
        self.assertEqual("/account", response.headers["Location"])
        self.assertIsNotNone(User.query.filter_by(email="new-user@example.test").first())
        self.assertEqual(405, self.client.get("/logout").status_code)
        self.client.post("/logout")
        response = self.client.post("/login", data={"email": "new-user@example.test", "password": "TestPass123!"})
        self.assertEqual("/account", response.headers["Location"])

    def test_revised_help_answers_are_in_detail_not_search_cards(self) -> None:
        results = self.client.get("/support?q=tracking")
        self.assertNotIn(b"event time and event location", results.data)
        detail = self.client.get("/support/shipment-exception-status")
        self.assertIn(b"event time and event location", detail.data)
        self.assertIn(b"Operational delay", detail.data)
        weather = self.client.get("/support/weather-delay-guidance")
        self.assertIn(b"not a promised delivery time", weather.data)

    def test_rate_estimate_rejects_non_numeric_weight_without_server_error(self) -> None:
        response = self.client.post(
            "/rate-estimate",
            data={
                "origin_state": "CA",
                "destination_state": "TX",
                "weight_lb": "not-a-number",
                "package_type": "Box",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Enter a weight between", response.data)

    def test_submitted_quote_produces_verifiable_result_url(self) -> None:
        response = self.client.post(
            "/rate-estimate",
            data={
                "origin_state": "CA",
                "destination_state": "TX",
                "weight_lb": "8",
                "package_type": "Box",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRegex(response.location, r"^/rate-estimate\?quote=[A-Za-z0-9_.-]+$")
        result = self.client.get(response.location)
        self.assertEqual(200, result.status_code)

        # The expected quote, the answer text and the screenshots are all derived
        # or generated here, so this test never restates a graded answer.
        sys.path.insert(0, str(SITE_ROOT / "verify"))
        from ground_truth import task_ground_truth  # noqa: E402
        from PIL import Image  # noqa: E402

        truth = task_ground_truth(TEST_DB_PATH, 3)
        cheapest = truth["cheapest"]
        answer = (f"The cheapest displayed service is {cheapest['name']}, at "
                  f"${cheapest['price']:,.2f}.")
        self.assertIn(cheapest["name"].encode(), result.data)
        self.assertIn(f"${cheapest['price']:,.2f}".encode(), result.data)

        trajectory = {
            "task_id": "FedEx--3",
            "steps": [
                {
                    "url": "http://localhost:40024/rate-estimate",
                    "action": "click",
                    "params": {"index": 9},
                    "screenshot_before": "step_000.png",
                    "screenshot_after": "step_001.png",
                    "action_result": {
                        "is_done": False,
                        "success": True,
                        "error": None,
                        "extracted_content": "Clicked",
                    },
                },
                {
                    "url": f"http://localhost:40024{response.location}",
                    "action": "done",
                    "params": {"text": answer, "success": True},
                    "screenshot_before": "step_001.png",
                    "screenshot_after": "step_002.png",
                },
            ],
            "final_answer": answer,
        }
        with tempfile.TemporaryDirectory() as run_dir:
            shots = Path(run_dir) / "screenshots"
            shots.mkdir()
            for index in range(3):
                Image.new("RGB", (1280, 800), (247, 244, 251)).save(shots / f"step_{index:03d}.png")
            (Path(run_dir) / "trajectory.json").write_text(json.dumps(trajectory))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SITE_ROOT / "verify" / "verify_3.py"),
                    "--run_dir",
                    run_dir,
                    "--initial_db",
                    str(TEST_DB_PATH),
                    "--after_db",
                    str(TEST_DB_PATH),
                    "--no_llm",
                    "true",
                ],
                cwd=SITE_ROOT.parents[1],
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_ship_rejects_invalid_numeric_values_without_server_error(self) -> None:
        self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "TestPass123!"},
        )
        valid_form = {
            "recipient_name": "Regression Recipient",
            "origin_city": "Seattle",
            "origin_state": "WA",
            "destination_city": "Austin",
            "destination_state": "TX",
            "package_type": "Box",
            "weight_lb": "5",
            "declared_value": "100",
            "pickup_mode": "dropoff",
        }

        for field, invalid_value, message in (
            ("weight_lb", "not-a-number", b"Enter a weight between"),
            ("declared_value", "not-a-number", b"Enter a declared value between"),
        ):
            with self.subTest(field=field):
                form = {**valid_form, field: invalid_value}
                response = self.client.post("/ship", data=form)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.data)
                # A rejected draft must not poison the later steps of the flow.
                self.assertEqual(302, self.client.get("/ship/service", follow_redirects=False).status_code)
                self.assertNotEqual(500, self.client.get("/ship/service").status_code)

    def test_shipment_review_uses_the_readable_handoff_label(self) -> None:
        self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "TestPass123!"},
        )
        self.client.post(
            "/ship",
            data={
                "recipient_name": "Regression Recipient",
                "origin_city": "Seattle",
                "origin_state": "WA",
                "destination_city": "Austin",
                "destination_state": "TX",
                "package_type": "Box",
                "weight_lb": "5",
                "declared_value": "100",
                "pickup_mode": "dropoff",
            },
        )
        self.client.post("/ship/service", data={"service_slug": "fedex-2day"})

        response = self.client.get("/ship/review")

        self.assertEqual(200, response.status_code)
        self.assertIn(b"Drop off at staffed location", response.data)
        self.assertNotIn(b">Dropoff<", response.data)

    def test_pickup_rejects_non_numeric_package_count_without_server_error(self) -> None:
        self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "TestPass123!"},
        )
        # No location is pre-selected, so the window list is empty until one is
        # chosen. Pick the first seeded location rather than naming one here.
        slug = db.session.execute(
            db.select(site.Location.slug).order_by(site.Location.slug)).scalars().first()
        self.assertIsNotNone(slug)
        bare_page = self.client.get("/pickup")
        self.assertNotRegex(
            bare_page.data, rb'name="pickup_slot_id".*?<option value="\d+"',
            "the window list must stay empty until a location is chosen")

        pickup_page = self.client.get(f"/pickup?location_slug={slug}")
        slot_match = re.search(
            rb'name="pickup_slot_id".*?<option value="(\d+)"',
            pickup_page.data,
            re.DOTALL,
        )
        self.assertIsNotNone(slot_match)

        response = self.client.post(
            "/pickup",
            data={
                "location_slug": slug,
                "pickup_slot_id": slot_match.group(1).decode(),
                "package_count": "not-a-number",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Enter a package count between 1 and", response.data)

    def test_pickup_location_change_uses_get_navigation_without_creating_a_request(self) -> None:
        self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "TestPass123!"},
        )
        before_count = db.session.execute(db.select(db.func.count()).select_from(PickupRequest)).scalar_one()

        response = self.client.get("/pickup")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"window.location.href", response.data)
        self.assertNotIn(b"this.form.submit()", response.data)
        after_count = db.session.execute(db.select(db.func.count()).select_from(PickupRequest)).scalar_one()
        self.assertEqual(after_count, before_count)

    def test_location_detail_exposes_posted_hours(self) -> None:
        sys.path.insert(0, str(SITE_ROOT / "verify"))
        from ground_truth import task_ground_truth  # noqa: E402

        expected = task_ground_truth(TEST_DB_PATH, 14)
        response = self.client.get(f"/locations/{expected['slug']}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(expected["hours"].encode(), response.data)
        self.assertIn(expected["name"].encode(), response.data)

    def test_packaged_asset_archive_has_no_appledouble_members(self) -> None:
        repository_root = SITE_ROOT.parents[1]
        with tempfile.TemporaryDirectory() as archive_dir:
            subprocess.run(
                [
                    str(repository_root / "scripts" / "extract_assets.sh"),
                    archive_dir,
                    "fedex",
                ],
                cwd=repository_root,
                check=True,
                capture_output=True,
                text=True,
            )
            with tarfile.open(Path(archive_dir) / "fedex.tar.gz", "r:gz") as archive:
                appledouble_members = [
                    name for name in archive.getnames() if Path(name).name.startswith("._")
                ]

        self.assertEqual(appledouble_members, [])

    def test_user_can_create_then_remove_a_local_demo_shipment(self) -> None:
        self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "TestPass123!"},
        )
        self.client.post(
            "/ship",
            data={
                "recipient_name": "Regression Recipient",
                "origin_city": "Seattle",
                "origin_state": "WA",
                "destination_city": "Austin",
                "destination_state": "TX",
                "package_type": "Box",
                "weight_lb": "5",
                "declared_value": "100",
                "pickup_mode": "dropoff",
            },
        )
        self.client.post("/ship/service", data={"service_slug": "fedex-2day"})
        confirmation = self.client.post("/ship/review", follow_redirects=True)
        shipment_match = re.search(rb"SH-\d+", confirmation.data)
        tracking_match = re.search(rb"FDX\d+", confirmation.data)
        self.assertIsNotNone(shipment_match)
        self.assertIsNotNone(tracking_match)
        shipment_code = shipment_match.group().decode()
        tracking_number = tracking_match.group()

        account_page = self.client.get("/account/shipments")
        self.assertIn(tracking_number, account_page.data)

        removal = self.client.post(
            f"/account/shipments/{shipment_code}/remove",
            follow_redirects=True,
        )

        self.assertEqual(removal.status_code, 200)
        self.assertIn(b"Removed local demo shipment", removal.data)
        self.assertNotIn(tracking_number, removal.data)
        self.assertNotIn(tracking_number, self.client.get("/account/shipments").data)


if __name__ == "__main__":
    unittest.main()
