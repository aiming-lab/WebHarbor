#!/usr/bin/env python3
"""Generate asset_inventory.json for the megabus mirror.

asset_inventory.json is the tracked manifest checked by the image build's
scripts/check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256 and the real upstream
source URL it was downloaded from. Source URLs come from image_manifest.json,
which records the exact us.megabus.com URL each byte stream was fetched from
on the snapshot date.

Run from sites/megabus/: python3 build_inventory.py [--check-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
IMG = HERE / "static" / "images"
MANAGED_ROOTS = ("static/images", "static/external_cache")

SNAPSHOT = "2026-09-23"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    manifest = json.loads((HERE / "image_manifest.json").read_text(encoding="utf-8"))
    by_path = {}
    for row in manifest:
        rel = row["path"]
        if rel in by_path:
            raise SystemExit(f"duplicate manifest path: {rel}")
        by_path[rel] = row["url"]

    actual = {}
    for root in MANAGED_ROOTS:
        base = HERE / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.name != ".gitkeep":
                actual[str(path.relative_to(HERE))] = path

    missing = sorted(set(by_path) - set(actual))
    extra = sorted(set(actual) - set(by_path))
    if missing:
        print("manifest paths missing on disk:", missing[:10], file=sys.stderr)
    if extra:
        print("files on disk missing from manifest:", extra[:10], file=sys.stderr)
    if missing or extra:
        return 1

    assets = []
    for rel in sorted(actual):
        path = actual[rel]
        data = path.read_bytes()
        assets.append({
            "path": rel,
            "bytes": len(data),
            "sha256": sha256(path),
            "source_url": by_path[rel],
        })

    inventory = {
        "schema_version": 1,
        "site": "megabus",
        "asset_count": len(assets),
        "total_bytes": sum(a["bytes"] for a in assets),
        "captured_on": SNAPSHOT,
        "capture_method": "Playwright-rendered pages + direct HTTP fetches of the resolved media URLs",
        "source_page": "https://us.megabus.com/",
        "notes": [
            "Covers every managed media file under static/images/; the seed database is deterministically generated at build time from the tracked source_data_*.json snapshots (see .build-generated-seed).",
            "Every entry is byte- and hash-verified by scripts/check_asset_inventory.py during the Docker build.",
            "All source URLs are real upstream media URLs served by us.megabus.com as rendered on the snapshot date.",
        ],
        "assets": assets,
    }
    if args.check_only:
        print(f"[check] {len(assets)} inventoried assets cover static/images/ exactly")
        return 0
    (HERE / "asset_inventory.json").write_text(json.dumps(inventory, indent=1), encoding="utf-8")
    print(f"wrote asset_inventory.json: {len(assets)} assets, "
          f"{inventory['total_bytes']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
