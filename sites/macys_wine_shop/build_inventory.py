#!/usr/bin/env python3
"""Generate asset_inventory.json for the macys_wine_shop mirror.

asset_inventory.json is the tracked manifest enforced by the image build's
check_asset_inventory.py gate: every file under static/images/ (and
static/external_cache/ when present) with its byte length, SHA-256, and the
real upstream source URL it was harvested from. Source URLs come from the
harvest manifest (scraped_data/image_manifest.json).

The script also cross-checks the seed DB: every image path the seed
references (product images, case-bottle thumbnails, home/banner images)
must exist on disk, so the mirror never ships a broken <img>.

Run from sites/macys_wine_shop/: python3 build_inventory.py [--check-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
STATIC = HERE / "static"
MANAGED_ROOTS = ("static/images", "static/external_cache")
HARVEST_MANIFEST = HERE / "scraped_data" / "image_manifest.json"
SEED = HERE / "instance_seed" / "macys_wine_shop.db"
OUT = HERE / "asset_inventory.json"

IMG_ROOTS = [STATIC / "images", STATIC / "external_cache"]


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_harvest_manifest() -> dict:
    if HARVEST_MANIFEST.exists():
        return json.loads(HARVEST_MANIFEST.read_text(encoding="utf-8"))
    return {}


def seed_image_references() -> set[str]:
    """Image paths referenced by the seed DB, relative to static/images."""
    import sqlite3

    if not SEED.exists():
        return set()
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    referenced: set[str] = set()
    try:
        rows = connection.execute(
            "SELECT path FROM product_images UNION ALL "
            "SELECT image_path FROM case_bottles").fetchall()
        for (path,) in rows:
            if path and path.startswith("/static/images/"):
                referenced.add(path.removeprefix("/static/images/"))
        # home section assets are embedded in home_sections.data_json
        for (raw,) in connection.execute("SELECT data_json FROM home_sections"):
            data = json.loads(raw or "{}")
            for value in _iter_strings(data):
                if value.startswith("/static/images/"):
                    referenced.add(value.removeprefix("/static/images/"))
        for (raw,) in connection.execute("SELECT image_path FROM blog_articles"):
            if raw:
                referenced.add(raw)
    finally:
        connection.close()
    return referenced


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    harvest = load_harvest_manifest()
    assets = []
    referenced = seed_image_references()
    missing_refs = set()
    for ref in sorted(referenced):
        candidate = STATIC / "images" / ref
        if not candidate.exists():
            missing_refs.add(ref)

    for root in IMG_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = "static/" + str(path.relative_to(STATIC))
            if "/images/" in rel:
                key = rel.split("/images/", 1)[1]
                source = harvest.get(key, "")
            else:
                source = harvest.get(rel, "")
            assets.append({
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": source,
            })

    if missing_refs:
        print(f"[inventory] ERROR: seed references {len(missing_refs)} missing files:",
              file=sys.stderr)
        for ref in sorted(missing_refs)[:10]:
            print("   ", ref, file=sys.stderr)
        return 2

    no_source = [a for a in assets if not a["source_url"]]
    if no_source:
        print(f"[inventory] WARNING: {len(no_source)} assets lack upstream source URLs")
        for a in no_source[:5]:
            print("   ", a["path"])

    if args.check_only:
        print(f"[inventory] check-only: {len(assets)} inventoried assets")
        return 0

    inventory = {
        "schema_version": 1,
        "site": "macys_wine_shop",
        "snapshot_date": "2026-09-22",
        "asset_count": len(assets),
        "assets": assets,
    }
    OUT.write_text(json.dumps(inventory, indent=1, ensure_ascii=False) + "\n")
    total = sum(a["bytes"] for a in assets)
    print(f"[inventory] wrote {len(assets)} assets, {total / 1e6:.1f} MB -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
