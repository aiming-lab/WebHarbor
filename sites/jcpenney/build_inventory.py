#!/usr/bin/env python3
"""Generate asset_inventory.json for the jcpenney mirror.

asset_inventory.json is the tracked manifest checked by the image build's
check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256, and the real upstream
source URL it was downloaded from. Source URLs come from the harvest
manifest (scraped_data/assets_manifest.json).

The script also cross-checks the seed DB: every product image and swatch
the seed references must exist on disk (no broken <img> tags), and it warns
about downloaded files nothing references so orphans can be pruned before
the inventory is written.

Run from sites/jcpenney/: python3 build_inventory.py [--check-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
STATIC = HERE / "static"
MANAGED_ROOTS = ("static/images", "static/external_cache")
HARVEST_MANIFEST = HERE / "scraped_data" / "assets_manifest.json"
SEED = HERE / "instance_seed" / "jcpenney.db"
OUT = HERE / "asset_inventory.json"


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


def seed_references() -> tuple[set[str], set[str]]:
    """Referenced product/swatch paths (relative to static/images) + missing ones."""
    referenced: set[str] = set()
    missing: set[str] = set()
    if not SEED.exists():
        return referenced, missing
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT p.ppid, pi.filename FROM product_images pi "
            "JOIN products p ON p.id = pi.product_id").fetchall()
        for ppid, filename in rows:
            rel = f"products/{ppid}/{filename}"
            (referenced if (STATIC / "images" / rel).is_file() else missing).add(rel)
        rows = connection.execute(
            "SELECT p.ppid, pc.swatch_file FROM product_colors pc "
            "JOIN products p ON p.id = pc.product_id WHERE pc.swatch_file != ''").fetchall()
        for ppid, swatch in rows:
            rel = f"swatches/{ppid}/{swatch}"
            (referenced if (STATIC / "images" / rel).is_file() else missing).add(rel)
    finally:
        connection.close()
    return referenced, missing


def template_image_references() -> set[str]:
    """Collect /static/images/... paths and inline image filenames referenced by
    the Jinja templates (homepage tiles render through Jinja set-lists, so both
    literal paths and bare filenames are collected)."""
    import re
    refs: set[str] = set()
    for template in (HERE / "templates").rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        for match in re.finditer(r"/static/images/([A-Za-z0-9_\-./]+)", text):
            refs.add(match.group(1))
        for match in re.finditer(r'["\']([A-Za-z0-9_\-]+\.(?:jpg|jpeg|png|webp))["\']', text):
            refs.add(match.group(1))
    for source in (HERE / "static" / "css").rglob("*.css"):
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"/static/images/([A-Za-z0-9_\-./]+)", text):
            refs.add(match.group(1))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="do not write asset_inventory.json, just report")
    args = parser.parse_args()

    harvest = load_harvest_manifest()
    referenced, missing = seed_references()
    if missing:
        print(f"[inventory] ERROR: seed references {len(missing)} missing files:",
              file=sys.stderr)
        for rel in sorted(missing)[:10]:
            print(f"  static/images/{rel}", file=sys.stderr)
        return 1

    template_refs = template_image_references()
    # category hero images live in source_data.json but render through templates
    source = json.loads((HERE / "source_data.json").read_text(encoding="utf-8"))
    hero_refs = {f"home/{row['hero_image']}" for row in source.get("categories", [])
                 if row.get("hero_image")}

    assets = []
    unreferenced = []
    for root in MANAGED_ROOTS:
        base = HERE / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = str(path.relative_to(HERE))
            key = path.relative_to(HERE / "static" / "images").as_posix() \
                if root == "static/images" else None
            harvest_row = harvest.get(key) if key else None
            source_url = (harvest_row or {}).get("source_url", "")
            if not source_url:
                print(f"[inventory] ERROR: no upstream source URL for {rel}",
                      file=sys.stderr)
                return 1
            data = path.read_bytes()
            if harvest_row and (harvest_row.get("bytes") != len(data)
                                or harvest_row.get("sha256") != hashlib.sha256(data).hexdigest()):
                print(f"[inventory] ERROR: {rel} does not match its recorded download",
                      file=sys.stderr)
                return 1
            assets.append({
                "path": rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_url": source_url,
            })
            if key and key not in referenced and key not in template_refs \
                    and key not in hero_refs:
                # bare filenames collected from templates may live in any dir
                if key.rsplit("/", 1)[-1] in template_refs:
                    pass
                else:
                    unreferenced.append(key)

    if unreferenced:
        print(f"[inventory] WARNING: {len(unreferenced)} on-disk files are referenced "
              f"by neither the seed nor the templates:")
        for rel in unreferenced[:15]:
            print(f"  static/images/{rel}")
        print("[inventory] prune them before shipping the archive")

    payload = {
        "schema_version": 1,
        "site": "jcpenney",
        "note": ("Real imagery captured from jcpenney.com and its sc-images.jcpenney.com / "
                  "www.mkt-jcpenney.com asset hosts; every file lists its upstream source URL."),
        "asset_count": len(assets),
        "assets": assets,
    }
    if not args.check_only:
        OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"[inventory] {len(assets)} assets inventoried across {MANAGED_ROOTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
