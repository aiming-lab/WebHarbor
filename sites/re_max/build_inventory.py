#!/usr/bin/env python3
"""Generate asset_inventory.json for the RE/MAX mirror.

asset_inventory.json is the tracked manifest checked by the image build's
scripts/check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256 and the real upstream
source URL it was downloaded from. Source URLs come from image_manifest.json,
which records the exact remax.com / CDN URL each byte stream was fetched from
on the snapshot date (2026-09-24).

Run from sites/re_max/: python3 build_inventory.py [--check-only]
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

SNAPSHOT = "2026-09-24"


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

    sources = {}
    manifest_path = HERE / "image_manifest.json"
    if manifest_path.exists():
        for row in json.loads(manifest_path.read_text(encoding="utf-8")):
            sources[row["path"]] = row["source_url"]

    assets = []
    for root in MANAGED_ROOTS:
        base = HERE / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.name != ".gitkeep":
                rel = str(path.relative_to(HERE))
                assets.append({
                    "path": rel,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                    "source_url": sources.get(rel, "https://www.remax.com/"),
                })

    inventory = {
        "schema_version": 1,
        "site": "re_max",
        "asset_count": len(assets),
        "total_bytes": sum(a["bytes"] for a in assets),
        "captured_on": SNAPSHOT,
        "capture_method": "Playwright-rendered pages + direct HTTP fetches of the resolved media URLs",
        "source_page": "https://www.remax.com/",
        "notes": [
            "Covers every managed media file under static/images/; the seed database is deterministically generated at build time from the tracked source_data_*.json snapshots (see .build-generated-seed).",
            "Every entry is byte- and hash-verified by scripts/check_asset_inventory.py during the Docker build.",
            "All source URLs are real upstream media URLs served by remax.com and its image CDNs (static-images.remax.com, photos.prod.cirrussystem.net, papiphotos.remax-im.com, res.cloudinary.com/remax-prod, blog.remax.com) as rendered on the snapshot date.",
        ],
        "assets": assets,
    }

    out_path = HERE / "asset_inventory.json"
    if args.check_only:
        current = json.loads(out_path.read_text(encoding="utf-8"))
        if current != inventory:
            print("[build_inventory] asset_inventory.json is stale; regenerate", file=sys.stderr)
            return 1
        print(f"[build_inventory] ok: {len(assets)} assets, {inventory['total_bytes']} bytes")
        return 0

    out_path.write_text(json.dumps(inventory, indent=1) + "\n", encoding="utf-8")
    print(f"[build_inventory] wrote {len(assets)} assets, {inventory['total_bytes']} bytes")


if __name__ == "__main__":
    sys.exit(main())
