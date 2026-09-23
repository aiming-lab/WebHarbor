#!/usr/bin/env python3
"""Generate asset_inventory.json + provenance.json for the Google Shopping mirror.

asset_inventory.json is the tracked manifest checked by the image build's
`check_asset_inventory.py` gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256, and the real upstream
source URL it was downloaded from.

provenance.json documents each tracked path's provenance classification,
mirroring the flightaware reference structure.
"""
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CAPTURE = HERE / "scraped_data" / "captured_products.json"
SITE_ROOT = HERE

DEPT_URL = "https://www.gstatic.com/shopping/departments/{}_672px.png"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    state = json.loads(CAPTURE.read_text())
    products = state["products"]

    # source URLs per image, recovered from the capture records
    product_src = {}
    favicon_src = {}
    for title, rec in products.items():
        import hashlib as _h
        pid = "gs" + _h.sha1(title.encode()).hexdigest()[:16]
        if rec.get("img"):
            product_src[pid] = rec["img"]
        if rec.get("favicon"):
            merchant = rec.get("merchant") or "store"
            mslug = re.sub(r"[^a-z0-9]+", "_", merchant.lower()).strip("_")
            favicon_src[mslug] = rec["favicon"]

    assets = []
    managed_roots = ("static/images", "static/external_cache")
    for root in managed_roots:
        root_dir = SITE_ROOT / root
        if not root_dir.exists():
            continue
        for path in sorted(root_dir.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = str(path.relative_to(SITE_ROOT)).replace("/", "/")
            slug = path.stem
            if rel.startswith("static/images/departments/"):
                src = DEPT_URL.format(slug.replace("dept_", ""))
            elif rel.startswith("static/images/products/"):
                stem = path.stem
                if stem in product_src:
                    src = product_src[stem]
                else:
                    raise SystemExit(f"no known upstream source for {rel}")
            elif rel.startswith("static/images/favicons/"):
                stem = path.stem
                if stem in favicon_src:
                    src = favicon_src[stem]
                else:
                    raise SystemExit(f"no known upstream source for {rel}")
            else:
                raise SystemExit(f"no known upstream source for {rel}")
            assets.append({
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": src,
            })

    inventory = {"schema_version": 1, "asset_count": len(assets),
                 "assets": assets}
    (SITE_ROOT / "asset_inventory.json").write_text(
        json.dumps(inventory, indent=1) + "\n")

    provenance = {
        "schema_version": 1,
        "snapshot_date": "2026-09-22",
        "records": [
            {"path": "app.py", "classification": "mirror-code",
             "scope": "Flask application implementing the shopping.google.com mirror: the 'For you' homepage feed, the Departments grid, scored search with filters and sorting, product detail pages with merchant offers and Save/Track price actions, the Deals page, the captured 'Nothing to see here' empty state, and the signed-in shopping list + price tracking surfaces. Route and nav structure follow the upstream site (Search tab -> departments, Nearby, Deals, For you)."},
            {"path": "seed_data.py", "classification": "mirror-code",
             "scope": "Deterministic build-time and boot-time seeder. All content rows come from the tracked _seed_catalog.py snapshot; benchmark users use a frozen bcrypt hash so the SQLite seed is byte-reproducible on every build."},
            {"path": "_seed_catalog.py", "classification": "captured-upstream-content",
             "scope": "Product cards captured from the live shopping.google.com 'For you' feed on 2026-09-22: real titles, merchants, current prices, was-prices, discount badges, and the per-section headings/subheadings/explore queries exactly as served. The 15 departments and their tile imagery come from the live /shopping/departments page."},
            {"path": "asset_inventory.json", "classification": "asset-manifest",
             "scope": "Per-file inventory (bytes, SHA-256, upstream source URL) for every managed image under static/images/; enforced by the image build's check_asset_inventory.py gate."},
            {"path": "static/images/products/", "classification": "captured-upstream-content",
             "scope": "Real product images served by Google's shopping CDN (encrypted-tbn*.gstatic.com/shopping) as displayed on the captured 'For you' feed cards; downloaded at their resolved URLs."},
            {"path": "static/images/favicons/", "classification": "captured-upstream-content",
             "scope": "Real merchant favicons served by Google's favicon CDN (encrypted-tbn*.gstatic.com/favicon-tbn) as displayed next to merchant names on the captured feed cards."},
            {"path": "static/images/departments/", "classification": "captured-upstream-content",
             "scope": "The 15 department tile images served by www.gstatic.com/shopping/departments as displayed on the live /shopping/departments grid."},
            {"path": "static/icons/", "classification": "captured-upstream-content",
             "scope": "The Google Shopping favicon (gstatic shoppingpage casa home_60dp.png), the multicolor Google G mark (googleg_standard_color_128dp.png), and the real upstream empty-state illustration (the 400x218 PNG embedded in the captured search empty page) referenced by the captured upstream pages; the shopping-bag tab glyph is the inline SVG served by the upstream homepage."},
            {"path": "templates/", "classification": "mirror-code",
             "scope": "Jinja templates reproducing the captured upstream layout: header with the Google Shopping wordmark + 'Shop for anything' search pill, the Search/Nearby/Deals/For you tab row, 24px-radius feed section cards with 48px Google Sans headings, Explore pill buttons, product cards with badge/tile/title/merchant/price rows, the departments grid, the product panel, and the footer location line captured from the live site."},
            {"path": "scraped_data/", "classification": "build-time-only",
             "scope": "Recon and capture tooling plus raw page captures (gitignored, never shipped): the homepage/departments HTML the design was extracted from, the live collector that rotated the 'For you' feed, and the replayer that rebuilds the tracked catalog from the captures."},
        ],
    }
    (SITE_ROOT / "provenance.json").write_text(
        json.dumps(provenance, indent=1) + "\n")
    print(f"inventory: {len(assets)} assets")


if __name__ == "__main__":
    main()
