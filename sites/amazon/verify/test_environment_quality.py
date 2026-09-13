"""Regression checks for the accepted Amazon grading contract."""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1]
SEED_DB = SITE_DIR / "instance_seed" / "amazon_store.db"
ACCEPTED = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 21, 22, 27, 30, 39, 40)


class EnvironmentQualityTests(unittest.TestCase):
    def test_tasks_have_one_to_one_verifier_and_rubric(self) -> None:
        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(20, len(rows))
        self.assertEqual([f"Amazon--{number}" for number in ACCEPTED], [row["id"] for row in rows])
        self.assertEqual(len(rows), len({row["id"] for row in rows}))
        for number, row in zip(ACCEPTED, rows):
            self.assertEqual("http://localhost:40001/", row["web"])
            self.assertEqual(f"sites/amazon/verify/verify_{number}.py", row["verifier_path"])
            self.assertGreaterEqual(len(row["judge_rubric"]), 200)
            self.assertTrue((SITE_DIR.parents[1] / row["verifier_path"]).is_file())
        scripts = sorted(path.name for path in (SITE_DIR / "verify").glob("verify_[0-9]*.py"))
        expected = sorted(f"verify_{number}.py" for number in ACCEPTED)
        self.assertEqual(expected, scripts)

    def test_seed_supports_catalog_and_state_tasks(self) -> None:
        connection = sqlite3.connect(f"file:{SEED_DB}?mode=ro", uri=True)
        try:
            self.assertEqual(407, connection.execute("SELECT COUNT(*) FROM products").fetchone()[0])
            demo = connection.execute("SELECT id FROM users WHERE email='demo@amazon.com'").fetchone()
            self.assertIsNotNone(demo)
            user_id = demo[0]
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM wishlist_items WHERE user_id=?", (user_id,)).fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM cart_items WHERE user_id=?", (user_id,)).fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM products WHERE slug='women-s-izod-swingflex-golf-polo'").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM products WHERE slug='apple-iphone-12-pro-128gb'").fetchone()[0])
        finally:
            connection.close()

    def test_ranked_ground_truth_has_required_distractors(self) -> None:
        connection = sqlite3.connect(f"file:{SEED_DB}?mode=ro", uri=True)
        try:
            self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM products WHERE subcategory='Climbing'").fetchone()[0], 8)
            self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM products WHERE name LIKE '%Nintendo Switch Lite%' AND condition='Used - Good'").fetchone()[0], 3)
            self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM products WHERE subcategory='USB-C Hubs'").fetchone()[0], 6)
            self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM products WHERE subcategory='Fiction' AND release_date LIKE '2024-%'").fetchone()[0], 5)
            cheapest = connection.execute("SELECT slug FROM products WHERE name LIKE '%Nintendo Switch Lite%' AND condition='Used - Good' ORDER BY price,id LIMIT 1").fetchone()[0]
            self.assertEqual("nintendo-switch-lite-gray", cheapest)
        finally:
            connection.close()

    def test_search_implements_every_task_filter_and_sort(self) -> None:
        source = (SITE_DIR / "app.py").read_text(encoding="utf-8")
        for parameter in (
            "min_price", "max_price", "min_rating", "brand", "condition",
            "color", "size", "feature", "bestseller", "sort",
        ):
            self.assertIn(f"request.args.get('{parameter}'", source)
        for sort_key in ("price_asc", "price_desc", "rating", "bestseller"):
            self.assertIn(sort_key, source)

    def test_no_appledouble_files_are_present(self) -> None:
        self.assertEqual([], [path for path in SITE_DIR.rglob("*") if path.name.startswith("._")])


if __name__ == "__main__":
    unittest.main()
