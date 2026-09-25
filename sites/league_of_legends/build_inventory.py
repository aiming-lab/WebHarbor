#!/usr/bin/env python3
"""Generate asset_inventory.json for the League of Legends mirror.

asset_inventory.json is the tracked manifest checked by the image build's
check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256, and the real upstream
source URL it was downloaded from. Source URLs come from the harvest manifest
(scraped_data/image_manifest.json), which records the exact upstream CDN
URL each byte stream was fetched from (ddragon, cmsassets.rgpub.io,
lol.dyn.riotcdn.net, am-a.akamaihd.net).

The script also cross-checks the seed DB: every portrait, splash, ability
icon/poster and news banner the seed references must exist on disk (no
broken <img> tags), and it warns about downloaded files nothing references
so orphans can be pruned before the inventory is written.

Run from sites/league_of_legends/: python3 build_inventory.py [--check-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
STATIC = HERE / "static"
MANAGED_ROOTS = ("static/images", "static/external_cache")
HARVEST_MANIFEST = HERE / "scraped_data" / "image_manifest.json"
SEED = HERE / "instance_seed" / "league_of_legends.db"
OUT = HERE / "asset_inventory.json"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_harvest_manifest() -> dict:
    if HARVEST_MANIFEST.exists():
        return json.loads(HARVEST_MANIFEST.read_text(encoding="utf-8"))
    return {}


def seed_references() -> tuple[set[str], set[str]]:
    """Referenced image paths (relative to static/images) + missing ones."""
    referenced: set[str] = set()
    missing: set[str] = set()
    if not SEED.exists():
        return referenced, missing
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        def add(rel: str | None) -> None:
            if not rel:
                return
            (referenced if (STATIC / "images" / rel).is_file() else missing).add(rel)
        for portrait, splash in connection.execute(
                "SELECT portrait, splash FROM champions"):
            add(portrait)
            add(splash)
        for icon, poster in connection.execute("SELECT icon, poster FROM abilities"):
            add(icon)
            add(poster)
        for splash, in connection.execute("SELECT splash FROM skins"):
            add(splash)
        for banner, in connection.execute("SELECT banner FROM articles"):
            add(banner)
        # article body inline images: /static/images/<path> references
        for body, in connection.execute(
                "SELECT body_html FROM articles WHERE external_url = ''"):
            if not body:
                continue
            index = 0
            while True:
                index = body.find("/static/images/", index)
                if index < 0:
                    break
                start = index + len("/static/images/")
                end = body.find('"', start)
                if end < 0:
                    break
                add(body[start:end])
                index = end
    finally:
        connection.close()
    return referenced, missing


def article_slugs() -> set[str]:
    slugs: set[str] = set()
    if not SEED.exists():
        return slugs
    uri = f"file:{SEED.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        for slug, in connection.execute("SELECT slug FROM articles"):
            slugs.add(slug)
    finally:
        connection.close()
    return slugs


def template_image_references() -> set[str]:
    """Collect literal /static/images/... paths, CSS url() targets and the
    champion-tile paths the classic roster template builds dynamically
    (classic_champions.html loops over app.py's CLASSIC_CHAMPIONS)."""
    import re
    refs: set[str] = set()
    for template in (HERE / "templates").rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        for match in re.finditer(r"/static/images/([A-Za-z0-9_\-./]+)", text):
            refs.add(match.group(1))
        for match in re.finditer(r"filename=['\"]images/([A-Za-z0-9_\-./]+)", text):
            refs.add(match.group(1))
    for source in (HERE / "static" / "css").rglob("*.css"):
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"\.\./images/([A-Za-z0-9_\-./]+)", text):
            refs.add(match.group(1))
    app_source = (HERE / "app.py").read_text(encoding="utf-8")
    block = re.search(r"CLASSIC_CHAMPIONS = \((.*?)\)\n\n", app_source, re.S)
    if block:
        for slug in re.findall(r'\("[^"]+", "([a-z]+)"\)', block.group(1)):
            refs.add(f"classic/champ_tiles/{slug}.jpg")
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="do not write asset_inventory.json, just report")
    args = parser.parse_args()

    harvest = load_harvest_manifest()
    referenced, missing = seed_references()
    if missing:
        print(f"[inventory] ERROR: seed references {len(missing)} missing files:",
              file=sys.stderr)
        for rel in sorted(missing)[:10]:
            print(f"  static/images/{rel}", file=sys.stderr)
        return 1

    template_refs = template_image_references()
    slugs = article_slugs()
    # news card images render as images/news/<slug>_card.jpg from every grid
    card_refs = {f"news/{slug}_card.jpg" for slug in slugs}

    assets = []
    unreferenced = []
    for root in MANAGED_ROOTS:
        base = HERE / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = str(path.relative_to(HERE))
            key = path.relative_to(HERE / "static" / "images").as_posix() \
                if root == "static/images" else None
            source_url = harvest.get(key, "") if key else ""
            if not source_url:
                print(f"[inventory] ERROR: no upstream source URL for {rel}",
                      file=sys.stderr)
                return 1
            data = path.read_bytes()
            assets.append({
                "path": rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_url": source_url,
            })
            if key and key not in referenced and key not in template_refs \
                    and key not in card_refs:
                unreferenced.append(key)

    if unreferenced:
        print(f"[inventory] WARNING: {len(unreferenced)} on-disk files are referenced "
              f"by neither the seed nor the templates:")
        for rel in unreferenced[:15]:
            print(f"  static/images/{rel}")
        print("[inventory] prune them before shipping the archive")
        return 1

    payload = {
        "schema_version": 1,
        "site": "league_of_legends",
        "note": ("Real imagery captured from leagueoflegends.com and its Riot asset "
                 "hosts (ddragon.leagueoflegends.com, cmsassets.rgpub.io, "
                 "lol.dyn.riotcdn.net, am-a.akamaihd.net); every file lists the "
                 "exact upstream URL it was downloaded from."),
        "asset_count": len(assets),
        "assets": assets,
    }
    if not args.check_only:
        OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"[inventory] {len(assets)} assets inventoried across {MANAGED_ROOTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
