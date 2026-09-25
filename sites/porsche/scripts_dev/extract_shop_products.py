#!/usr/bin/env python3
"""Extract shop_products.json offline from cached shop category pages.

Each category page embeds window[Symbol.for("InstantSearchInitialResults")]
with the Algolia response (48 rich hits per category: sku, name, slug, images,
prices, brand, stock, categories). Run from sites/porsche/.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRAPE = BASE / "scraped_data"

CATS = {
    "accessories": "Vehicle Accessories",
    "clothing": "Clothing",
    "home": "Home & Lifestyle",
}


def instant_blob(html: str) -> dict:
    i = html.find('window[Symbol.for("InstantSearchInitialResults")] = ')
    start = html.find("{", i)
    depth = 0
    j = start
    in_str = False
    esc = False
    while j < len(html):
        c = html[j]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"' and not in_str:
            in_str = True
        elif c == '"' and in_str:
            in_str = False
        elif c == "{" and not in_str:
            depth += 1
        elif c == "}" and not in_str:
            depth -= 1
            if depth == 0:
                break
        j += 1
    return json.loads(html[start : j + 1])


def main():
    products = {}
    for cat, cat_label in CATS.items():
        f = SCRAPE / f"shop_{cat}.html"
        if not f.exists():
            print(f"missing {f}")
            continue
        data = instant_blob(f.read_text())
        key = next(iter(data))
        results = data[key].get("results", [])
        hits = []
        for r in results:
            hits.extend(r.get("hits", []))
        n = 0
        for h in hits:
            oid = re.sub(r"\s+", "-", str(h.get("objectID") or "").strip())
            if not oid or oid in products:
                continue
            slug = str(h.get("slug") or "").strip().lstrip("-")
            if not slug:
                slug = re.sub(r"[^a-z0-9]+", "-", (h.get("name") or "").lower()).strip("-")
            price = h.get("grossPriceValue") or {}
            products[oid] = {
                "object_id": oid,
                "name": h.get("name", ""),
                "sku": (h.get("sku") or "").strip(),
                "slug": slug,
                "shop_category": cat_label,
                "main_category": (h.get("mainCategory") or {}).get("name", ""),
                "categories": [c.get("name", "") for c in h.get("categories", [])],
                "description": re.sub(r"<[^>]+>", " ", h.get("description") or "").strip(),
                "price_cents": price.get("centAmount", 0),
                "currency": price.get("currencyCode", "USD"),
                "brand": h.get("brand", ""),
                "in_stock": bool(h.get("isInStock")),
                "images": (h.get("images") or [])[:4],
                "color": [c.get("name", "") for c in (h.get("facetColor") or []) if isinstance(c, dict)],
                "size": h.get("size", ""),
                "labels": [l.get("name", "") if isinstance(l, dict) else l for l in (h.get("labels") or [])],
            }
            n += 1
        print(cat, "hits:", len(hits), "new:", n)
    out = sorted(products.values(), key=lambda p: p["object_id"])
    # de-duplicate slugs: append the object id when two products share one
    seen = {}
    for p in out:
        base = p["slug"] or p["object_id"]
        if base in seen:
            p["slug"] = f"{base}-{p['object_id']}".lower()
        else:
            seen[base] = True
            p["slug"] = base
    (SCRAPE / "shop_products.json").write_text(json.dumps(out, indent=1))
    print("TOTAL:", len(out))


if __name__ == "__main__":
    main()
