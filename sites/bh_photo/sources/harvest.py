#!/usr/bin/env python3
"""Harvest B&H catalog facts from Internet Archive snapshots of bhphotovideo.com.

The live site answers automated requests with a bot challenge, so every fact in
this mirror's seed is taken from a dated Wayback Machine capture instead. Each
record keeps the capture URL and timestamp so a reviewer can open the same page.

Only catalog facts are harvested: product name, brand, B&H SKU, manufacturer
part number, price, availability, condition, description and the published
specification table. Customer reviews, questions, accounts and orders are NOT
harvested; the mirror generates those as declared benchmark-synthetic state.

Usage:
    python3 harvest.py discover  --prefixes 15,16,17,18,19 --out candidates.json
    python3 harvest.py fetch     --candidates candidates.json --raw-dir RAW --out catalog.json
    python3 harvest.py images    --catalog catalog.json --out-dir IMG --manifest asset_inventory.json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0 Safari/537.36"

# Mirror subcategory -> keywords matched against the archived product URL slug.
CATEGORY_QUERIES = {
    "mirrorless-cameras": ["mirrorless"],
    "dslr-cameras": ["dslr", "eos_5d", "eos_6d", "d850", "d780"],
    "camera-lenses": ["_lens", "lens_"],
    "tripods-supports": ["tripod", "monopod", "gimbal"],
    "memory-cards-storage": ["sdxc", "cfexpress", "microsd", "_ssd"],
    "cinema-cameras": ["cinema_camera", "cinema_"],
    "drones": ["drone", "quadcopter"],
    "monitors-recorders": ["field_monitor", "recorder_monitor", "atomos"],
    "microphones": ["microphone", "_mic_", "shotgun"],
    "headphones": ["headphone"],
    "laptops": ["macbook", "_laptop", "thinkpad", "xps_"],
    "monitors": ["_monitor_", "display_monitor"],
    "printers-scanners": ["printer", "scanner"],
    "lighting-kits": ["_light_", "led_light", "softbox", "strobe"],
}


def get(url: str, timeout: int = 90) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def cdx_prefix(prefix: str, limit: int, since: str) -> list[tuple[str, str]]:
    """Pull one page of the archive index for product IDs starting with `prefix`.

    Server-side regex filtering across the whole product namespace times out, so
    the index is pulled in ID-prefix blocks and filtered locally. B&H product IDs
    ascend with recency, so higher prefixes reach current gear.
    """
    params = {
        "url": f"bhphotovideo.com/c/product/{prefix}",
        "matchType": "prefix",
        "output": "text",
        "fl": "timestamp,original",
        "filter": "statuscode:200",
        "collapse": "urlkey",
        "limit": str(limit),
        "from": since,
    }
    query = urllib.parse.urlencode(params, doseq=True)
    rows = []
    for line in get(f"{CDX}?{query}").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        timestamp, original = parts
        if "?" in original or not original.endswith(".html"):
            continue
        if original.rstrip("/").count("/") > 6:
            continue
        rows.append((timestamp, original))
    return rows


def classify(url: str) -> str | None:
    """Map an archived product URL slug onto one of the mirror's subcategories."""
    slug = url.rsplit("/", 1)[-1].lower()
    for subcategory, keywords in CATEGORY_QUERIES.items():
        if any(keyword in slug for keyword in keywords):
            return subcategory
    return None


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", " | ", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(fragment).strip()


def unwayback(url: str | None) -> str | None:
    """Turn an archive-rewritten asset URL back into its original address."""
    if not url:
        return None
    match = re.search(r"/web/\d+(?:[a-z_]+)?/(https?://.*)$", url)
    return match.group(1) if match else url


def parse_product(page: str, archive_url: str, original_url: str, timestamp: str) -> dict | None:
    product = None
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(html.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "Product":
                product = item
                break
        if product:
            break
    if not product:
        return None

    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price")
    try:
        price = float(price) if price not in (None, "") else None
    except (TypeError, ValueError):
        price = None

    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")

    # The specification block does not label every group on every page, so the
    # rows are collected across the whole block and each one is attributed to the
    # nearest preceding group heading.
    specs = []
    block = page
    start = page.find('productSpecs_')
    if start != -1:
        end = page.find('class="reviews_', start)
        block = page[start:end if end != -1 else len(page)]
    groups = [(m.start(), strip_tags(m.group(1))) for m in re.finditer(
        r'data-selenium="specsItemGroupName"[^>]*>(.*?)</div>', block, re.S)]
    for row in re.finditer(
        r'data-selenium="specsItemGroupTableColumnLabel"[^>]*>(.*?)</td>.*?'
        r'data-selenium="specsItemGroupTableColumnValue"[^>]*>(.*?)</td>',
        block, re.S,
    ):
        label, value = strip_tags(row.group(1)), strip_tags(row.group(2))
        if not label or not value:
            continue
        group_name = "Specifications"
        for position, name in groups:
            if position < row.start():
                group_name = name
            else:
                break
        specs.append({"group": group_name, "label": label, "value": value})

    images = product.get("image")
    if isinstance(images, str):
        images = [images]
    images = [unwayback(u) for u in (images or [])]

    return {
        "name": html.unescape(str(product.get("name") or "")).strip(),
        "brand": brand,
        "bh_sku": product.get("sku"),
        "mpn": product.get("mpn"),
        "description": strip_tags(str(product.get("description") or ""))[:1200] or None,
        "price_usd": price,
        "price_currency": offers.get("priceCurrency"),
        "availability": (offers.get("availability") or "").rsplit("/", 1)[-1] or None,
        "item_condition": (offers.get("itemCondition") or "").rsplit("/", 1)[-1] or None,
        "images": images,
        "specs": specs,
        "source": {
            "original_url": original_url,
            "archive_url": archive_url,
            "archive_timestamp": timestamp,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }


def cmd_discover(args: argparse.Namespace) -> int:
    candidates: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for prefix in args.prefixes.split(","):
        prefix = prefix.strip()
        if not prefix:
            continue
        try:
            rows = cdx_prefix(prefix, args.per_prefix, args.since)
        except Exception as error:  # noqa: BLE001 - report and continue
            print(f"  ! prefix {prefix}: {error}", file=sys.stderr)
            continue
        matched = 0
        for timestamp, original in rows:
            subcategory = classify(original)
            if not subcategory:
                continue
            matched += 1
            counts[subcategory] = counts.get(subcategory, 0) + 1
            candidates.setdefault(original, {
                "original_url": original, "archive_timestamp": timestamp,
                "subcategory": subcategory,
            })
        print(f"  prefix {prefix}: {len(rows)} archived pages, {matched} classified", file=sys.stderr)
        time.sleep(args.delay)
    Path(args.out).write_text(json.dumps(list(candidates.values()), indent=1))
    for subcategory in sorted(counts, key=counts.get, reverse=True):
        print(f"    {subcategory:26s} {counts[subcategory]}", file=sys.stderr)
    print(f"{len(candidates)} unique candidate product pages -> {args.out}")
    return 0


def cmd_reparse(args: argparse.Namespace) -> int:
    """Rebuild the catalog from cached pages, without touching the network."""
    candidates = {c["original_url"]: c for c in json.loads(Path(args.candidates).read_text())}
    catalog = []
    misses = 0
    for cache in sorted(Path(args.raw_dir).glob("*.html")):
        page = cache.read_text(encoding="utf-8", errors="replace")
        original = next((u for u in candidates
                         if re.sub(r"[^A-Za-z0-9]+", "_", u)[-120:] + ".html" == cache.name), None)
        if not original:
            misses += 1
            continue
        candidate = candidates[original]
        timestamp = candidate["archive_timestamp"]
        record = parse_product(page, f"{WAYBACK}/{timestamp}/{original}", original, timestamp)
        if not record or not record["name"]:
            misses += 1
            continue
        record["subcategory"] = candidate["subcategory"]
        catalog.append(record)
    Path(args.out).write_text(json.dumps(catalog, indent=1))
    counts = [len(r["specs"]) for r in catalog]
    print(f"{len(catalog)} products reparsed ({misses} unmatched) -> {args.out}")
    print(f"  specs: min {min(counts)} median {sorted(counts)[len(counts)//2]} max {max(counts)} "
          f"| under 4: {sum(1 for c in counts if c < 4)}")
    return 0


def cmd_images(args: argparse.Namespace) -> int:
    """Download the archived product photography referenced by the catalog.

    Wayback serves the original bytes under the `im_` modifier, so each image
    keeps the pixels the upstream product page showed at capture time.
    """
    catalog = json.loads(Path(args.catalog).read_text())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    saved = skipped = failed = 0
    for record in catalog:
        images = record.get("images") or []
        if not images:
            continue
        sku = record.get("bh_sku") or record["source"]["original_url"].rsplit("/", 2)[1]
        key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(sku)).strip("-").lower()
        target = out_dir / f"{key}.jpg"
        if key in manifest and target.exists():
            skipped += 1
            continue
        timestamp = record["source"]["archive_timestamp"]
        # the page's own capture may predate any capture of its image, so fall
        # back to the nearest capture the archive holds
        attempts = [f"{WAYBACK}/{timestamp}im_/{images[0]}",
                    f"{WAYBACK}/2026im_/{images[0]}",
                    f"{WAYBACK}/im_/{images[0]}"]
        try:
            blob = None
            last_error: Exception | None = None
            for image_url in attempts:
                try:
                    request = urllib.request.Request(image_url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(request, timeout=90) as response:
                        candidate_blob = response.read()
                    if len(candidate_blob) < 2000 or not candidate_blob.startswith((b"\xff\xd8", b"\x89PNG")):
                        raise ValueError(f"not an image ({len(candidate_blob)} bytes)")
                    blob = candidate_blob
                    break
                except Exception as attempt_error:  # noqa: BLE001 - try the next capture
                    last_error = attempt_error
                    time.sleep(args.delay)
            if blob is None:
                raise last_error or ValueError("no capture found")
            target.write_bytes(blob)
            manifest[key] = {
                "file": f"images/products/{key}.jpg",
                "bytes": len(blob),
                "sha256": __import__("hashlib").sha256(blob).hexdigest(),
                "original_image_url": images[0],
                "archive_image_url": image_url,
                "product": record["name"],
            }
            saved += 1
            print(f"  {saved:4d} {key:28s} {len(blob)//1024:5d} KB  {record['name'][:46]}", file=sys.stderr)
            time.sleep(args.delay)
        except Exception as error:  # noqa: BLE001
            failed += 1
            print(f"  ! {key}: {error}", file=sys.stderr)
        if saved % 10 == 0:
            manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    print(f"images saved={saved} reused={skipped} failed={failed} -> {out_dir}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    candidates = json.loads(Path(args.candidates).read_text())
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    catalog = json.loads(out_path.read_text()) if out_path.exists() else []
    done = {record["source"]["original_url"] for record in catalog}

    for index, candidate in enumerate(candidates, 1):
        original = candidate["original_url"]
        if original in done:
            continue
        if args.limit and len(catalog) >= args.limit:
            break
        timestamp = candidate["archive_timestamp"]
        archive_url = f"{WAYBACK}/{timestamp}/{original}"
        cache = raw_dir / (re.sub(r"[^A-Za-z0-9]+", "_", original)[-120:] + ".html")
        try:
            page = cache.read_text(encoding="utf-8", errors="replace") if cache.exists() else get(archive_url)
            if not cache.exists():
                cache.write_text(page, encoding="utf-8")
                time.sleep(args.delay)
        except Exception as error:  # noqa: BLE001
            print(f"  ! {index} {original[-60:]}: {error}", file=sys.stderr)
            continue
        record = parse_product(page, archive_url, original, timestamp)
        if not record or not record["name"]:
            print(f"  - {index} no product data: {original[-60:]}", file=sys.stderr)
            continue
        record["subcategory"] = candidate["subcategory"]
        catalog.append(record)
        done.add(original)
        if len(catalog) % 10 == 0:
            out_path.write_text(json.dumps(catalog, indent=1))
        print(f"  {len(catalog):4d} {record['brand']} | {record['name'][:58]} | "
              f"${record['price_usd']} | {len(record['specs'])} specs", file=sys.stderr)
    out_path.write_text(json.dumps(catalog, indent=1))
    print(f"{len(catalog)} products -> {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover")
    discover.add_argument("--out", default="candidates.json")
    discover.add_argument("--prefixes", default="15,16,17,18,19")
    discover.add_argument("--per-prefix", type=int, default=2500)
    discover.add_argument("--since", default="2026")
    discover.add_argument("--delay", type=float, default=1.0)
    discover.set_defaults(func=cmd_discover)

    fetch = sub.add_parser("fetch")
    fetch.add_argument("--candidates", default="candidates.json")
    fetch.add_argument("--raw-dir", required=True)
    fetch.add_argument("--out", default="catalog.json")
    fetch.add_argument("--limit", type=int, default=0)
    fetch.add_argument("--delay", type=float, default=1.5)
    fetch.set_defaults(func=cmd_fetch)

    images = sub.add_parser("images")
    images.add_argument("--catalog", default="catalog.json")
    images.add_argument("--out-dir", required=True)
    images.add_argument("--manifest", required=True)
    images.add_argument("--delay", type=float, default=1.0)
    images.set_defaults(func=cmd_images)

    reparse = sub.add_parser("reparse")
    reparse.add_argument("--candidates", required=True)
    reparse.add_argument("--raw-dir", required=True)
    reparse.add_argument("--out", required=True)
    reparse.set_defaults(func=cmd_reparse)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
