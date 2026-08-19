from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_ROOT))
TEST_TEMP_DIR = tempfile.TemporaryDirectory()
TEST_DB_PATH = Path(TEST_TEMP_DIR.name) / "fedex-test.db"
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"
os.environ["FEDEX_DATABASE_URI"] = f"sqlite:///{TEST_DB_PATH}"

from app import app, db  # noqa: E402
from seed_data import seed_benchmark_users, seed_database  # noqa: E402


class FedExRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls) -> None:
        TEST_TEMP_DIR.cleanup()

    def setUp(self) -> None:
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

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

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enter a weight greater than 0", response.data)

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
            ("weight_lb", "not-a-number", b"Enter a weight greater than 0"),
            ("declared_value", "not-a-number", b"Enter a declared value of at least 0"),
        ):
            with self.subTest(field=field):
                form = {**valid_form, field: invalid_value}
                response = self.client.post("/ship", data=form, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(message, response.data)

    def test_pickup_rejects_non_numeric_package_count_without_server_error(self) -> None:
        self.client.post(
            "/login",
            data={"email": "alice.j@test.com", "password": "TestPass123!"},
        )
        pickup_page = self.client.get("/pickup")
        slot_match = re.search(
            rb'name="pickup_slot_id".*?<option value="(\d+)"',
            pickup_page.data,
            re.DOTALL,
        )
        self.assertIsNotNone(slot_match)

        response = self.client.post(
            "/pickup",
            data={
                "location_slug": "seattle-downtown-wa",
                "pickup_slot_id": slot_match.group(1).decode(),
                "package_count": "not-a-number",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enter a package count of at least 1", response.data)

    def test_generated_svg_assets_are_valid_xml(self) -> None:
        svg_paths = sorted((SITE_ROOT / "static" / "images").glob("*.svg"))
        self.assertGreater(len(svg_paths), 0)

        invalid_paths = []
        for svg_path in svg_paths:
            try:
                ET.parse(svg_path)
            except ET.ParseError:
                invalid_paths.append(svg_path.name)

        self.assertEqual(invalid_paths, [])

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
