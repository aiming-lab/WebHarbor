#!/usr/bin/env python3
"""Regenerate asset_inventory.json for every managed runtime image.

Each row records the shipped file's byte count, SHA-256, and the upstream
source URL it was captured from (plus whether it was Pillow-resized from a
larger upstream original).
"""
from __future__ import annotations
import hashlib, json, pathlib

SITE = pathlib.Path(__file__).resolve().parent
MANAGED_ROOTS = ("static/images", "static/external_cache")

def main() -> None:
    curation = json.loads((SITE / "scraped_data" / "image_curation.json").read_text())
    raw_meta = curation["raw_meta"]
    rows = []
    for root in MANAGED_ROOTS:
        base = SITE / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = str(path.relative_to(SITE))
            data = path.read_bytes()
            source_url, resized = "", False
            for raw_name, dest in curation["mapping"].items():
                if dest and rel.endswith(dest):
                    source_url = raw_meta[raw_name]["url"]
                    resized = curation["shipped"][dest]["resized"]
                    break
            if not source_url:
                raise SystemExit(f"no upstream source recorded for {rel}")
            rows.append({
                "path": rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_url": source_url,
                "resized_from_upstream_original": resized,
            })
    manifest = {
        "schema_version": 1,
        "asset_count": len(rows),
        "total_bytes": sum(r["bytes"] for r in rows),
        "assets": rows,
    }
    (SITE / "asset_inventory.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"asset_inventory.json: {len(rows)} assets, {manifest['total_bytes']/1e6:.1f} MB")

if __name__ == "__main__":
    main()
