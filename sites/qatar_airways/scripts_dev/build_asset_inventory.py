#!/usr/bin/env python3
"""Build sites/qatar_airways/asset_inventory.json from the harvested image tree.

Walks static/images/ (the HF-managed roots), maps every file back to its
real upstream qatarairways.com source URL, and records bytes + sha256 per
file. Provenance resolution order:

  1. source_data/image_source_urls.json — the frozen per-path actual byte
     source map written by scripts_dev/harvest_assets.py. For files whose
     main rendition has no Wayback capture this records the
     same-destination fallback URL that really produced the bytes, so the
     inventory's source_url is the true origin, never a nominal one.
  2. the harvest manifest (a file fetched straight from its own URL keeps
     its own URL as the source).

The inventory is enforced at Docker build time by
scripts/check_asset_inventory.py (exact coverage, per-file hash, https
source, format framing) — proving every shipped image is the real upstream
asset captured at a real CDN path.
"""
import hashlib
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent

spec = importlib.util.spec_from_file_location("harvest_assets", HERE / "harvest_assets.py")
harvest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harvest)


def main() -> int:
    manifest = harvest.build_manifest()
    path_to_url = {}
    for entry in manifest:
        for p in entry["paths"]:
            path_to_url.setdefault(p["path"], entry["url"])

    # frozen actual-source map wins: it carries the URL that produced the
    # bytes for fallback-written files (and equals the nominal URL for the
    # rest, so it is authoritative for every path it lists)
    source_map_path = SITE / "source_data" / "image_source_urls.json"
    source_map = json.loads(source_map_path.read_text()) if source_map_path.exists() else {}

    site_root = SITE
    assets = []
    missing = []
    for root in ("static/images",):
        for path in sorted((site_root / root).rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = path.relative_to(site_root).as_posix()
            # manifest paths are relative to static/images/
            key = rel[len("static/images/"):] if rel.startswith("static/images/") else rel
            url = source_map.get(key) or path_to_url.get(key)
            if not url:
                missing.append(rel)
                continue
            data = path.read_bytes()
            assets.append({
                "path": rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_url": url,
            })
    if missing:
        print(f"[inventory] ERROR: {len(missing)} files without a source URL:",
              file=sys.stderr)
        for m in missing[:20]:
            print("   ", m, file=sys.stderr)
        return 1
    inv = {"schema_version": 1, "asset_count": len(assets), "assets": assets}
    out = site_root / "asset_inventory.json"
    out.write_text(json.dumps(inv, indent=1))
    print(f"[inventory] wrote {out} with {len(assets)} assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
