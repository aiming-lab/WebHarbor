"""Regression checks for Target review findings."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SITE_DIR.parents[1]
SEED_DB = SITE_DIR / "instance_seed" / "target.db"


def connection(path: Path = SEED_DB) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


class EnvironmentQualityTests(unittest.TestCase):
    def test_site_registration_and_tasks_use_port_40018(self) -> None:
        startup = (REPO_ROOT / "websyn_start.sh").read_text(encoding="utf-8")
        self.assertIn("ikea phys_org target", startup)
        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(20, len(rows))
        for index, row in enumerate(rows):
            self.assertEqual(f"Target--{index}", row["id"])
            self.assertEqual("http://localhost:40018/", row["web"])
            self.assertEqual(f"sites/target/verify/verify_{index}.py", row["verifier_path"])

    def test_seed_corrections_are_present(self) -> None:
        db = connection()
        try:
            bob_cart = db.execute("SELECT COUNT(*) FROM cart_items c JOIN users u ON u.id=c.user_id WHERE u.email='bob.c@test.com'").fetchone()[0]
            self.assertEqual(0, bob_cart)
            target = db.execute("SELECT p.pickup_eligible,si.quantity FROM products p JOIN store_inventory si ON si.product_id=p.id JOIN stores s ON s.id=si.store_id WHERE p.sku='TGT85566854' AND s.slug='denver-stapleton'").fetchone()
            self.assertEqual((1, 5), tuple(target))
            for sku in ("TGT13374157", "TGT13374348"):
                specs = json.loads(db.execute("SELECT specs_json FROM products WHERE sku=?", (sku,)).fetchone()[0])
                section = next(section for section in specs if section["title"] == "Nutrition Facts — entire 2-pizza package")
                sodium = next(item for item in section["items"] if item["label"] == "Sodium — package total")
                self.assertIn(sodium["value"], {"1950mg", "1750mg"})
        finally:
            db.close()

    def test_task_6_filters_change_the_first_result(self) -> None:
        db = connection()
        try:
            base = "FROM products p JOIN categories c ON c.id=p.category_id JOIN brands b ON b.id=p.brand_id WHERE c.slug='pets' AND b.slug='boots-barkley' AND p.list_price>p.price"
            unfiltered = db.execute(f"SELECT p.sku {base} ORDER BY p.price,p.rating DESC LIMIT 1").fetchone()[0]
            filtered = db.execute(f"SELECT p.sku {base} AND p.pickup_eligible=1 ORDER BY p.price,p.rating DESC LIMIT 1").fetchone()[0]
        finally:
            db.close()
        self.assertNotEqual(unfiltered, filtered)
        self.assertEqual("TGT90310046", filtered)

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="target-migration-") as temp_dir:
            database = Path(temp_dir) / "target.db"
            shutil.copy2(SEED_DB, database)
            db = sqlite3.connect(database)
            try:
                db.execute("UPDATE products SET pickup_eligible=0,delivery_eligible=0 WHERE sku='TGT85566854'")
                db.execute("INSERT INTO cart_items(id,user_id,product_id,quantity,fulfillment_method,created_at) SELECT 999999,u.id,p.id,1,'delivery','2026-04-01' FROM users u,products p WHERE u.email='bob.c@test.com' AND p.sku='TGT85566854'")
                db.commit()
            finally:
                db.close()
            command = [sys.executable, str(SITE_DIR / "migrate_seed.py"), str(database)]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            first_hash = hashlib.sha256(database.read_bytes()).hexdigest()
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            second_hash = hashlib.sha256(database.read_bytes()).hexdigest()
            self.assertNotIn("0 rows changed", first.stdout)
            self.assertIn("0 rows changed", second.stdout)
            self.assertEqual(first_hash, second_hash)

    def test_post_forms_have_csrf_tokens(self) -> None:
        missing = []
        for template in (SITE_DIR / "templates").glob("*.html"):
            lines = template.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if "<form" not in line or 'method="post"' not in "\n".join(lines[index:index + 3]).lower():
                    continue
                if "csrf_token" not in "\n".join(lines[index:index + 7]):
                    missing.append(f"{template.name}:{index + 1}")
        self.assertEqual([], missing)

    def test_templates_remove_known_leaks_and_placeholders(self) -> None:
        templates = "\n".join(path.read_text(encoding="utf-8") for path in (SITE_DIR / "templates").glob("*.html"))
        self.assertNotIn('href="#"', templates)
        self.assertNotIn("alice.j@test.com /", templates)
        account = (SITE_DIR / "templates/account.html").read_text(encoding="utf-8")
        self.assertNotIn("recent_orders", account)
        self.assertNotIn("wishlist_preview", account)
        stores = (SITE_DIR / "templates/stores.html").read_text(encoding="utf-8")
        self.assertNotIn("store.address", stores)
        self.assertNotIn("store.amenities", stores)

    def test_no_appledouble_files_are_extracted(self) -> None:
        entries = [path for path in SITE_DIR.rglob("*") if path.name.startswith("._")]
        self.assertEqual([], entries)


if __name__ == "__main__":
    unittest.main()
