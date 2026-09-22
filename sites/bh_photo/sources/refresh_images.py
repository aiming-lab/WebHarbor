#!/usr/bin/env python3
"""Attach newly downloaded photography to the frozen catalog, in place.

Selection is deliberately not re-run. Once tasks and verifiers are written
against a manifest, changing which products it contains would invalidate them,
so this only fills in `image_path` for products already in the manifest.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--assets", required=True)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    assets = json.loads(Path(args.assets).read_text())

    added = 0
    for product in manifest["products"]:
        if product.get("image_path"):
            continue
        key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(product.get("bh_sku") or "")).strip("-").lower()
        asset = assets.get(key)
        if not asset:
            continue
        product["image_path"] = asset["file"]
        product["image_sha256"] = asset["sha256"]
        added += 1

    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    imaged = sum(1 for p in manifest["products"] if p.get("image_path"))
    print(f"attached {added} newly archived photos; {imaged}/{len(manifest['products'])} products imaged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
