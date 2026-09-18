"""Offline source and asset contract for the Best Buy mirror."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit


class SourceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.site = Path(
            os.environ.get("BESTBUY_SOURCE", Path(__file__).resolve().parents[1])
        )
        cls.catalog = json.loads((cls.site / "source_catalog.json").read_text(encoding="utf-8"))
        cls.items = [
            (batch, item)
            for batch in cls.catalog["batches"]
            for item in batch["items"]
        ]

    def test_catalog_has_complete_diverse_provenance(self) -> None:
        batches = self.catalog["batches"]
        self.assertEqual(self.catalog["schema_version"], 1)
        self.assertEqual(len(batches), 12)
        self.assertEqual(len(self.items), 125)
        self.assertEqual(len({item["sku"] for _, item in self.items}), 125)
        self.assertEqual(len({batch["category_slug"] for batch in batches}), 12)
        self.assertTrue(all(len(batch["items"]) >= 6 for batch in batches))
        self.assertTrue(all(batch["sourceUrl"].startswith("https://www.bestbuy.com/") for batch in batches))

    def test_every_product_and_image_is_source_pinned(self) -> None:
        for batch, item in self.items:
            with self.subTest(sku=item["sku"]):
                product_host = urlsplit(item["url"]).hostname
                image_host = urlsplit(item["image"]).hostname
                self.assertEqual(product_host, "www.bestbuy.com")
                self.assertTrue(item["url"].startswith("https://www.bestbuy.com/product/"))
                self.assertEqual(image_host, "pisces.bbystatic.com")
                self.assertRegex(item["sku"], r"^\d{7,8}$")
                self.assertRegex(item["price"], r"^\$[\d,]+\.\d{2}$")
                self.assertIn(item["content_type"], {"image/webp", "image/avif"})
                self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(item["byte_size"], 0)
                self.assertRegex(item["local_path"], rf"^images/products/{item['sku']}\.(?:webp|avif)$")
                self.assertEqual(batch["category_slug"], item.get("category_slug", batch["category_slug"]))

    def test_extracted_assets_match_catalog_when_present(self) -> None:
        existing = 0
        for _, item in self.items:
            path = self.site / "static" / item["local_path"]
            if not path.exists():
                continue
            existing += 1
            payload = path.read_bytes()
            self.assertEqual(len(payload), item["byte_size"], path)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"], path)
            if item["content_type"] == "image/webp":
                self.assertEqual(payload[:4], b"RIFF", path)
                self.assertEqual(payload[8:12], b"WEBP", path)
            else:
                self.assertEqual(payload[4:12], b"ftypavif", path)
        if (self.site / "static" / "images").exists():
            self.assertEqual(existing, len(self.items), "partially extracted source asset set")

    def test_seed_runtime_projects_the_source_catalog(self) -> None:
        seed = (self.site / "seed_data.py").read_text(encoding="utf-8")
        persist = seed[seed.index("def _persist_products"):seed.index("def _add_delivery_options")]
        self.assertIn("SOURCE_CATALOG_PATH", seed)
        self.assertIn("source_catalog", persist)
        self.assertNotIn("_generic_products", persist)
        self.assertNotRegex(persist, re.compile(r"products/.+\.svg"))


if __name__ == "__main__":
    unittest.main()
