#!/usr/bin/env python3
"""Build asset_inventory.json for the medicare_gov mirror.

Walks static/images (the pinned asset bundle's managed root for this site)
and records each file's byte length, SHA-256, and the upstream URL the file
was captured from on 2026-09-23 (scripts_dev/image_sources.json, written by
the Playwright harvest). scripts/check_asset_inventory.py validates the
inverse direction at image build time.

Usage (from sites/medicare_gov/):
    python3 scripts_dev/build_inventory.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
IMAGES = HERE / "static" / "images"
SOURCES = Path(__file__).resolve().parent / "image_sources.json"


def main() -> None:
    # image_sources.json maps upstream URL -> local filename (harvest order)
    url_to_name = json.loads(SOURCES.read_text(encoding="utf-8"))
    sources = {name: url for url, name in url_to_name.items()}
    rows = []
    for path in sorted(IMAGES.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        data = path.read_bytes()
        relative = path.relative_to(HERE).as_posix()
        source_url = sources.get(path.name)
        if not source_url:
            raise SystemExit(f"missing upstream source for {relative}")
        if relative.startswith("static/images/"):
            source_url = "https://www.medicare.gov" + source_url if source_url.startswith("/") else source_url
        rows.append({
            "path": relative,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_url": source_url,
        })
    manifest = {
        "schema_version": 1,
        "asset_count": len(rows),
        "assets": rows,
    }
    (HERE / "asset_inventory.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"asset_inventory.json: {len(rows)} assets")


if __name__ == "__main__":
    main()
