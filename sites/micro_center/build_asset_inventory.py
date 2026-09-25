#!/usr/bin/env python3
"""Generate asset_inventory.json for the micro_center site.

Every file under static/images and static/external_cache gets a row with a
byte count, SHA-256, and the upstream source URL it was fetched from.
Product images come from productimages.microcenter.com (fetched directly
from Micro Center's CDN); site chrome comes from Micro Center's static
asset CDN; fonts are Google Fonts Open Sans (SIL OFL).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parent
MANAGED_ROOTS = ("static/images", "static/external_cache")

RACK = ("https://60a99bedadae98078522-a9b6cded92292ef3bace063619038eb1.ssl.cf2.rackcdn.com")
FONTS = {
    "OpenSans-Regular.woff2": "https://fonts.gstatic.com/s/opensans/v44/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4taVIGxA.woff2",
    "OpenSans-SemiBold.woff2": "https://fonts.gstatic.com/s/opensans/v44/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsgH1x4taVIGxA.woff2",
    "OpenSans-Bold.woff2": "https://fonts.gstatic.com/s/opensans/v44/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsg-1x4taVIGxA.woff2",
}
SITE_CHROME = {
    "MClogoWhiteStacked.svg": f"{RACK}/MClogoWhiteStacked.svg",
    "storeWHITE.svg": f"{RACK}/storeWHITE.svg",
    "storeBLACK.svg": f"{RACK}/storeBLACK.svg",
    "chevron-downWhite.svg": f"{RACK}/chevron-downWhite.svg",
    "UWhite.svg": f"{RACK}/UWhite.svg",
    "ZOOM.svg": f"{RACK}/ZOOM.svg",
    "EPScart.svg": f"{RACK}/EPScart.svg",
    "0105MagnifyingGlassWHITE.svg": f"{RACK}/0105MagnifyingGlassWHITE.svg",
    "images_buttons_btn_closeModal.png": f"{RACK}/images_buttons_btn_closeModal.png",
}


def source_url_for(relative: str) -> str:
    parts = relative.split("/")
    if relative.startswith("static/images/site/"):
        return SITE_CHROME.get(parts[-1], f"{RACK}/{parts[-1]}")
    if relative.startswith("static/fonts/"):
        return FONTS.get(parts[-1], f"https://fonts.gstatic.com/s/opensans/{parts[-1]}")
    if relative.startswith("static/images/products/"):
        return f"https://productimages.microcenter.com/{parts[-1]}"
    return f"https://www.microcenter.com/{relative}"


def main() -> None:
    rows = []
    total = 0
    for root in MANAGED_ROOTS:
        base = SITE / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            relative = path.relative_to(SITE).as_posix()
            data = path.read_bytes()
            rows.append({
                "path": relative,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_url": source_url_for(relative),
            })
            total += len(data)
    manifest = {
        "schema_version": 1,
        "asset_count": len(rows),
        "total_bytes": total,
        "assets": rows,
    }
    out = SITE / "asset_inventory.json"
    out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"[inventory] {len(rows)} assets, {total/1024/1024:.1f} MB -> {out.name}")


if __name__ == "__main__":
    main()
