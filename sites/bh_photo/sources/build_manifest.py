#!/usr/bin/env python3
"""Turn harvested archive records into the reviewed source manifest the seed reads.

`harvest.py` writes one raw record per archived product page. This step selects
the records the mirror ships, derives the filter fields the app needs from the
published specification table (never by invention), and writes
`sites/bh_photo/source_catalog.json` with per-product provenance.

A field that cannot be read from the source is written as null. Downstream code
treats null as "not stated by the source" and the review report lists those gaps.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Upstream department labels, taken from the bhphotovideo.com nav strip.
DEPARTMENTS = {
    "photography": {
        "name": "Photography", "nav_order": 1,
        "children": ["mirrorless-cameras", "dslr-cameras", "camera-lenses",
                     "tripods-supports", "memory-cards-storage"],
    },
    "computers": {
        "name": "Computers", "nav_order": 2,
        "children": ["laptops", "monitors", "printers-scanners"],
    },
    "pro-video": {
        "name": "Pro Video", "nav_order": 3,
        "children": ["cinema-cameras", "monitors-recorders"],
    },
    "lighting": {"name": "Lighting", "nav_order": 4, "children": ["lighting-kits"]},
    "pro-audio": {"name": "Pro Audio", "nav_order": 5, "children": ["microphones", "headphones"]},
    "drones": {"name": "Drones", "nav_order": 6, "children": ["drones"]},
}

SUBCATEGORY_NAMES = {
    "mirrorless-cameras": "Mirrorless Cameras", "dslr-cameras": "DSLR Cameras",
    "camera-lenses": "Lenses", "tripods-supports": "Tripods & Support",
    "memory-cards-storage": "Memory Cards & Storage", "cinema-cameras": "Cinema Cameras",
    "monitors-recorders": "Monitors & Recorders", "microphones": "Microphones",
    "headphones": "Headphones", "laptops": "Laptops", "monitors": "Monitors",
    "printers-scanners": "Printers & Scanners", "lighting-kits": "Lighting",
    "drones": "Drones",
}

PRODUCT_TYPES = {
    "mirrorless-cameras": "Mirrorless Camera", "dslr-cameras": "DSLR Camera",
    "camera-lenses": "Lens", "tripods-supports": "Tripod", "memory-cards-storage": "Storage",
    "cinema-cameras": "Cinema Camera", "monitors-recorders": "Field Monitor",
    "microphones": "Microphone", "headphones": "Headphones", "laptops": "Laptop",
    "monitors": "Monitor", "printers-scanners": "Printer", "lighting-kits": "Light",
    "drones": "Drone",
}

# spec label -> manifest field. Labels are the ones B&H publishes.
SPEC_FIELDS = {
    "mount_type": ("Lens Mount", "Mount", "Lens Mount(s)"),
    "sensor_size": ("Sensor Type", "Sensor Size", "Image Sensor"),
    "focal_length": ("Focal Length", "Focal Length Range"),
    "connectivity": ("Connectivity", "Wireless", "Interface", "I/O"),
}


# The archive index is matched on URL slugs, which puts pouches, adapters and
# conferencing cameras into the wrong shelf. Classification is redone here from
# the product name, which is the text a shopper actually sees.
ACCESSORY_PATTERNS = re.compile(
    r"\b(pouch|case|bag|backpack|strap|cap|hood|cleaning|wipe|blower|screen protector|"
    r"battery grip|adapter ring|step-up|filter kit|lens cap|dust|plate only|l-bracket|"
    r"cable|extension kit|spare|replacement|refill|cartridge|toner|paper|ink)\b", re.I)

NAME_RULES = [
    ("drones", r"\b(drone|quadcopter)\b"),
    ("cinema-cameras", r"\bcinema camera\b"),
    ("mirrorless-cameras", r"\bmirrorless camera\b"),
    ("dslr-cameras", r"\bdslr\b"),
    ("memory-cards-storage", r"\b(cfexpress|sdxc|microsdxc|microsd|memory card|ssd|nas|card reader)\b"),
    ("laptops", r"\b(laptop|macbook|notebook)\b"),
    ("printers-scanners", r"\b(printer|scanner)\b"),
    ("headphones", r"\b(headphone|earphone|in-ear monitor)\b"),
    ("microphones", r"\b(microphone|shotgun mic|lavalier|wireless mic|\bmic\b)"),
    ("monitors-recorders", r"\b(field monitor|recorder|on-camera monitor)\b"),
    ("monitors", r"\bmonitor\b"),
    ("tripods-supports", r"\b(tripod|monopod|gimbal|slider|fluid head|support)\b"),
    ("lighting-kits", r"\b(led (panel|light|monolight)|softbox|light kit|monolight|strobe|"
                     r"light panel|cob light|spotlight)\b"),
    ("camera-lenses", r"\blens\b"),
]


def reclassify(record: dict) -> str | None:
    """Return the shelf a product belongs on, or None to drop it."""
    name = record.get("name") or ""
    if ACCESSORY_PATTERNS.search(name):
        return None
    for subcategory, pattern in NAME_RULES:
        if re.search(pattern, name, re.I):
            # a camera that merely ships "with ... Lens" is still a camera
            if subcategory == "camera-lenses" and re.search(r"\bcamera\b", name, re.I):
                return None
            return subcategory
    # no name rule matched: keep the shelf the archive URL implied
    return record.get("subcategory")


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-{2,}", "-", text).strip("-")[:200]


def spec_lookup(specs: list[dict], labels: tuple[str, ...]) -> str | None:
    for label in labels:
        for row in specs:
            if row["label"].strip().lower() == label.lower():
                return row["value"]
    return None


def parse_megapixels(specs: list[dict], name: str) -> float | None:
    """Read effective megapixels from the published sensor resolution row."""
    value = spec_lookup(specs, ("Sensor Resolution", "Effective Pixels", "Resolution"))
    if value:
        effective = re.search(r"Effective:\s*([\d.]+)\s*Megapixel", value, re.I)
        if effective:
            return float(effective.group(1))
        plain = re.search(r"([\d.]+)\s*(?:MP|Megapixel)", value, re.I)
        if plain:
            return float(plain.group(1))
    return None


def parse_capacity_gb(specs: list[dict], name: str) -> int | None:
    value = spec_lookup(specs, ("Capacity", "Storage Capacity", "Internal Storage"))
    for candidate in (value, name):
        if not candidate:
            continue
        match = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB)\b", candidate, re.I)
        if match:
            size = float(match.group(1))
            return int(size * 1024) if match.group(2).upper() == "TB" else int(size)
    return None


def condition_label(raw: str | None) -> str:
    return {"NewCondition": "New", "UsedCondition": "Used",
            "RefurbishedCondition": "Refurbished", "DamagedCondition": "Open-Box"}.get(raw or "", "New")


def availability_label(raw: str | None) -> str:
    return {"InStock": "In Stock", "OutOfStock": "Out of Stock",
            "Discontinued": "Discontinued", "PreOrder": "Pre-Order",
            "BackOrder": "Backordered"}.get(raw or "", "In Stock")


def select_subcategory(items: list[dict], limit: int, per_brand: int,
                       imaged: set[str] | None = None) -> list[dict]:
    """Pick a realistic shelf for one subcategory.

    A catalog that is all accessories makes price filters and comparisons
    meaningless, and a catalog that is all flagships has no distractors. Stocked
    items come first, the shelf is built from both ends of the price range, and
    no single brand may dominate it.
    """
    imaged = imaged or set()

    def has_image(record: dict) -> bool:
        key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(record.get("bh_sku") or "")).strip("-").lower()
        return key in imaged

    stocked = [r for r in items if (r.get("availability") or "") == "InStock"]
    pool = stocked or items
    # a shelf of placeholders is not a mirror: products whose photo the archive
    # actually holds are preferred, and the rest only fill what is left over
    with_photo = [r for r in pool if has_image(r)]
    without_photo = [r for r in pool if not has_image(r)]
    pool = with_photo + without_photo
    priced = sorted((r for r in pool if r.get("price_usd")),
                    key=lambda r: (not has_image(r), -r["price_usd"]))
    unpriced = [r for r in pool if not r.get("price_usd")]

    top_share = max(1, round(limit * 0.65))
    ordered = (priced[:top_share] + priced[-(limit - top_share):][::-1]
               if len(priced) > limit else list(priced))
    ordered += [r for r in priced if r not in ordered]
    ordered += unpriced

    chosen, brand_counts = [], defaultdict(int)
    for record in ordered:
        brand = (record.get("brand") or "?").lower()
        if brand_counts[brand] >= per_brand:
            continue
        brand_counts[brand] += 1
        chosen.append(record)
        if len(chosen) >= limit:
            break
    # if the brand cap starved the shelf, refill in price order
    if len(chosen) < limit:
        for record in ordered:
            if record not in chosen:
                chosen.append(record)
            if len(chosen) >= limit:
                break
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--assets", required=True, help="asset_inventory.json from harvest images")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-per-subcategory", type=int, default=14)
    parser.add_argument("--min-specs", type=int, default=4)
    parser.add_argument("--max-per-brand", type=int, default=4)
    args = parser.parse_args()

    records = json.loads(Path(args.catalog).read_text())
    assets = json.loads(Path(args.assets).read_text()) if Path(args.assets).exists() else {}
    imaged_keys = set(assets)

    by_subcategory: dict[str, list[dict]] = defaultdict(list)
    seen_names: set[str] = set()
    dropped: list[str] = []
    for record in records:
        name = (record.get("name") or "").strip()
        key = name.lower()
        if not name or key in seen_names:
            continue
        if len(record.get("specs") or []) < args.min_specs:
            continue
        subcategory = reclassify(record)
        if not subcategory:
            dropped.append(name)
            continue
        seen_names.add(key)
        record = dict(record, subcategory=subcategory)
        by_subcategory[subcategory].append(record)

    parent_of = {child: slug for slug, dept in DEPARTMENTS.items() for child in dept["children"]}
    products = []
    for subcategory, items in by_subcategory.items():
        for record in select_subcategory(items, args.max_per_subcategory,
                                         args.max_per_brand, imaged_keys):
            sku = record.get("bh_sku")
            asset_key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(sku or "")).strip("-").lower()
            asset = assets.get(asset_key)
            specs = record["specs"]
            products.append({
                "slug": slugify(record["name"]),
                "name": record["name"],
                "brand": record.get("brand") or "B&H",
                "bh_sku": sku,
                "mpn": record.get("mpn"),
                "department_slug": parent_of[subcategory],
                "subcategory_slug": subcategory,
                "product_type": PRODUCT_TYPES[subcategory],
                "price_usd": record.get("price_usd"),
                "availability": availability_label(record.get("availability")),
                "condition": condition_label(record.get("item_condition")),
                "description": record.get("description"),
                "mount_type": spec_lookup(specs, SPEC_FIELDS["mount_type"]),
                "sensor_size": spec_lookup(specs, SPEC_FIELDS["sensor_size"]),
                "focal_length": spec_lookup(specs, SPEC_FIELDS["focal_length"]),
                "connectivity": spec_lookup(specs, SPEC_FIELDS["connectivity"]),
                "megapixels": parse_megapixels(specs, record["name"]),
                "capacity_gb": parse_capacity_gb(specs, record["name"]),
                "image_path": asset["file"] if asset else None,
                "image_sha256": asset["sha256"] if asset else None,
                "specs": specs,
                "source": record["source"],
            })

    products.sort(key=lambda p: (p["department_slug"], p["subcategory_slug"], p["name"]))
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "upstream": "https://www.bhphotovideo.com/",
        "method": ("Catalog facts read from dated Internet Archive captures of bhphotovideo.com; "
                   "the live site answers automated requests with a bot challenge. Each product "
                   "record carries the capture URL and timestamp it was read from. Fields the "
                   "source does not state are null. Accounts, reviews, questions, bundles, store "
                   "locations, carts and orders are NOT sourced - they are declared "
                   "benchmark-synthetic state generated by seed_data.py."),
        "departments": DEPARTMENTS,
        "subcategory_names": SUBCATEGORY_NAMES,
        "product_count": len(products),
        "products": products,
    }
    Path(args.out).write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")

    with_price = sum(1 for p in products if p["price_usd"] is not None)
    with_image = sum(1 for p in products if p["image_path"])
    print(f"{len(products)} products -> {args.out}   ({len(dropped)} accessory/unclassified records dropped)")
    print(f"  priced {with_price}/{len(products)}   imaged {with_image}/{len(products)}   "
          f"specs avg {sum(len(p['specs']) for p in products)/max(1,len(products)):.1f}")
    for department, spec in DEPARTMENTS.items():
        count = sum(1 for p in products if p["department_slug"] == department)
        print(f"  {spec['name']:14s} {count:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
