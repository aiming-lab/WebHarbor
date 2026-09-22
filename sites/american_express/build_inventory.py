"""Scan templates + seed source for referenced static/images paths, prune the
rest, and write the tracked asset inventory manifest (asset_inventory.json).

The inventory covers static/images and static/external_cache exactly:
- path, bytes, sha256, source_url (the upstream URL each file was downloaded
  from, kept in scraped_data/images_manifest.json at build time).
Deterministic output (sorted paths).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent
IMAGES = SITE / "static" / "images"
CACHE = SITE / "external_cache"
MANIFEST = SITE / "asset_inventory.json"
PROVENANCE = SITE / "scraped_data" / "images_manifest.json"

STOP_WORDS = re.compile(r"")

def scan_references() -> set[str]:
    refs = set()
    for template in (SITE / "templates").glob("*.html"):
        text = template.read_text(encoding="utf-8")
        for m in re.finditer(r"images/([A-Za-z0-9_\-./]+?\.(?:png|jpg|jpeg|webp))", text):
            refs.add("static/images/" + m.group(1))
    for py in (SITE).glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in re.finditer(r"static/images/([A-Za-z0-9_\-./]+?\.(?:png|jpg|jpeg|webp))", text):
            refs.add("static/images/" + m.group(1))
    return refs

def main() -> int:
    if not PROVENANCE.exists():
        print("missing provenance manifest: scraped_data/images_manifest.json", file=sys.stderr)
        return 1
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    by_path = {row["path"]: row for row in provenance}

    refs = scan_references()
    print(f"referenced images: {len(refs)}")
    missing = sorted(p for p in refs if not (SITE / p).is_file())
    if missing:
        print("referenced but missing on disk:", file=sys.stderr)
        for p in missing:
            print("  ", p, file=sys.stderr)
        return 1

    # prune unreferenced files under static/images
    removed = 0
    freed = 0
    for path in sorted(IMAGES.rglob("*")):
        if path.is_dir() or path.name == ".gitkeep":
            continue
        rel = "static/images/" + path.relative_to(IMAGES).as_posix()
        if rel not in refs:
            freed += path.stat().st_size
            path.unlink()
            removed += 1
    print(f"pruned {removed} unreferenced files ({freed/1e6:.1f} MB)")

    # drop empty directories
    for path in sorted((p for p in IMAGES.rglob("*") if p.is_dir()), reverse=True):
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()
    CACHE.mkdir(exist_ok=True)

    # build inventory
    rows = []
    for path in sorted(list(IMAGES.rglob("*")) + list(CACHE.rglob("*"))):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        rel = path.relative_to(SITE).as_posix()
        data = path.read_bytes()
        row = {
            "path": rel,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        source = by_path.get(rel, {}).get("source_url")
        if not source:
            print(f"no provenance for {rel}", file=sys.stderr)
            return 1
        row["source_url"] = source
        rows.append(row)

    manifest = {
        "schema_version": 1,
        "site": "american_express",
        "note": "Real imagery captured from americanexpress.com and its aexp-static.com / icm.aexp-static.com asset hosts; every file lists its upstream source URL.",
        "asset_count": len(rows),
        "assets": rows,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(r["bytes"] for r in rows)
    print(f"inventory: {len(rows)} assets, {total/1e6:.1f} MB -> {MANIFEST.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
