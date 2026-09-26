#!/usr/bin/env python3
"""Generate asset_inventory.json for the ryanair mirror.

asset_inventory.json is the tracked manifest checked by the image build's
scripts/check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256 and the real upstream
source URL it was downloaded from. Source URLs come from image_manifest.json,
which records the exact www.ryanair.com URL each byte stream was fetched from
on the snapshot date (2026-09-24).

Run from sites/ryanair/: python3 build_inventory.py [--check-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
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
        raise SystemExit(f"manifest files missing on disk: {missing[:5]}")
    if extra:
        raise SystemExit(f"files on disk missing from manifest: {extra[:5]}")

    assets = []
    for rel, path in sorted(actual.items()):
        data = path.read_bytes()
        assets.append({
            "path": rel,
            "bytes": len(data),
            "sha256": sha256(path),
            "source_url": by_path[rel],
        })

    inventory = {
        "schema_version": 1,
        "site": "ryanair",
        "asset_count": len(assets),
        "total_bytes": sum(a["bytes"] for a in assets),
        "captured_on": SNAPSHOT,
        "capture_method": "Playwright-rendered pages + direct HTTP fetches of the resolved media URLs",
        "source_page": "https://www.ryanair.com/",
        "notes": [
            "Covers every managed media file under static/images/; the seed database is deterministically generated at build time from the tracked source_data_*.json snapshots (see .build-generated-seed).",
            "Every entry is byte- and hash-verified by scripts/check_asset_inventory.py during the Docker build.",
            "All source URLs are real upstream media URLs served by www.ryanair.com as rendered on the snapshot date.",
            "STN and LTN share one upstream asset: ryanair.com serves the same destination-card image bytes for both London airports.",
        ],
        "assets": assets,
    }
    out = HERE / "asset_inventory.json"
    if args.check_only:
        existing = json.loads(out.read_text(encoding="utf-8"))
        if existing != inventory:
            raise SystemExit("asset_inventory.json is out of date; rerun build_inventory.py")
        print(f"[check] asset_inventory.json matches {len(assets)} assets")
        return 0
    out.write_text(json.dumps(inventory, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"[build] wrote asset_inventory.json with {len(assets)} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
