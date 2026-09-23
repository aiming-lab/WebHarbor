#!/usr/bin/env python3
"""Build the tracked source_data.json from the harvested snapshots.

Reads scraped_data/{roster,champion_*,article_*}.json plus the merged news
listing and produces source_data.json: the deterministic input consumed by
seed_data.py. Article body HTML is rewritten so inline <img> tags point at
the locally downloaded copies under static/images/news/.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "scraped_data"
DEST = SITE / "source_data.json"
SPLASH_RE = re.compile(r"/splash/([A-Za-z0-9]+)_(\d+)\.jpg")


def load_manifest() -> dict:
    path = OUT / "image_manifest.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

SLOT_LABELS = {"P": "Passive", "Q": "Q", "W": "W", "E": "E", "R": "R"}


def slot_key(slot: str) -> str:
    slot = (slot or "").strip().upper()
    return {"PASSIVE": "P"}.get(slot, slot)


def build_champions() -> list[dict]:
    roster = {c["slug"]: c for c in json.loads((OUT / "roster.json").read_text())}
    manifest = load_manifest()
    champions = []
    for path in sorted(OUT.glob("champion_*.json")):
        data = json.loads(path.read_text())
        slug = data["slug"]
        masthead = data.get("masthead") or {}
        release_key = 0
        for ability in data.get("abilities", []):
            poster_url = ability.get("poster_url") or ""
            match = re.search(r"/champion-abilities/(\d+)/", poster_url)
            if match:
                release_key = int(match.group(1))
                break
        champion = {
            "slug": slug,
            "name": masthead.get("title") or roster[slug]["name"],
            "epithet": masthead.get("subtitle") or "",
            "roles": masthead.get("roles") or [],
            "difficulty_name": masthead.get("difficulty") or "Low",
            "difficulty_value": masthead.get("difficulty_value") or 1,
            "lore": masthead.get("description") or "",
            "release_key": release_key,
            "portrait": f"champions/{slug}_portrait.jpg",
            "splash": None,
            "abilities": [],
            "skins": [],
        }
        for i, skin in enumerate(data.get("skins", [])):
            url = skin.get("splash_url") or ""
            match = SPLASH_RE.search(url)
            num = int(match.group(2)) if match else i
            skin_record = {
                "num": num,
                "name": skin.get("name") or champion["name"],
                "splash": f"champions/{slug}_{num}_splash.jpg",
            }
            champion["skins"].append(skin_record)
            if num == 0:
                champion["splash"] = skin_record["splash"]
        for i, ability in enumerate(data.get("abilities", [])):
            key = slot_key(ability.get("slot"))
            icon_url = ability.get("icon_url") or ""
            ext = ".png" if ".png" in icon_url.lower() else (Path(urlsplit(icon_url).path).suffix or ".png")
            poster_url = ability.get("poster_url") or ""
            poster_path = f"abilities/{slug}_{key}_poster.jpg"
            champion["abilities"].append({
                "slot": key,
                "slot_label": SLOT_LABELS.get(key, key),
                "name": ability.get("name") or "",
                "description": ability.get("description") or "",
                "icon": f"abilities/{slug}_{key}_icon{ext}",
                "poster": poster_path if poster_url and poster_path in manifest else "",
                "sort": i,
            })
        champions.append(champion)
    champions.sort(key=lambda c: c["name"].lower())
    # de-duplicate skins on num (keeps the first occurrence) and drop skins
    # whose splash art failed to download (the live site references a few
    # ddragon URLs that 403 upstream — e.g. Fiddlesticks_27/37/46 — so the
    # mirror omits those carousel entries rather than shipping broken imgs)
    for champion in champions:
        seen: set[int] = set()
        skins = []
        for skin in champion["skins"]:
            if skin["num"] in seen:
                continue
            if skin["splash"] not in manifest:
                continue
            seen.add(skin["num"])
            skins.append(skin)
        champion["skins"] = skins
    return champions


def category_rows(items: list[dict]) -> list[dict]:
    titles = {
        "game-updates": "Game Updates",
        "dev": "Dev",
        "esports": "Esports",
        "community": "Community",
        "media": "Media",
        "merch": "Merch",
        "lore": "Lore",
        "riot_games": "Riot Games",
        "announcements": "Announcements",
        "patch-notes": "Patch Notes",
    }
    descriptions = {
        "game-updates": "The definitive source on all updates coming to the game.",
        "dev": "Explore the engine behind League and learn about the team building it.",
        "esports": "The latest from the world of League of Legends Esports.",
        "community": "Community creations, contests and collaborations.",
        "media": "Cinematics, trailers, music and more.",
        "merch": "The latest official League of Legends merch.",
        "lore": "Delve into the world of Runeterra through stories and comics.",
        "riot_games": "News from across Riot Games.",
        "announcements": "Official League of Legends announcements.",
        "patch-notes": "Every League of Legends patch, in one place.",
    }
    used = {item["category_machine"] for item in items}
    rows = []
    for machine_name, title in titles.items():
        rows.append({
            "machine_name": machine_name,
            "title": title,
            "description": descriptions[machine_name],
        })
    rows.sort(key=lambda r: r["machine_name"])
    return rows


def rewrite_inline_images(slug: str, body_html: str, inline_urls: list[str]) -> str:
    """Point inline <img> tags at the shared local copies under news/inline/.

    URLs whose download failed (absent from the manifest) are dropped from
    the body together with their <img> element so the page never references
    a missing file.
    """
    import hashlib
    manifest = load_manifest()
    for url in inline_urls:
        ext = Path(urlsplit(url).path).suffix
        if not ext or ext.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            if "f=" in (urlsplit(url).query or ""):
                inner = parse_qs(urlsplit(url).query).get("f", [""])[0]
                ext = Path(urlsplit(inner).path).suffix or ".jpg"
            else:
                ext = ".jpg"
        if ext.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            ext = ".jpg"
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        local_path = f"news/inline/{digest}{ext}"
        if local_path in manifest:
            body_html = body_html.replace(url, f"/static/images/{local_path}")
        else:
            pattern = re.compile(r"<img[^>]*src=\"" + re.escape(url) + r"\"[^>]*>")
            body_html = pattern.sub("", body_html)
    # upstream JSON sometimes lists an inline URL without the query string the
    # body carries (e.g. ?disposition=inline) or with HTML-encoded junk — strip
    # any residue that follows the rewritten local path so every src is clean.
    body_html = re.sub(
        r"(/static/images/news/inline/[0-9a-f]{12}\.(?:jpg|jpeg|png|gif|webp))"
        r"(?:\?[^\"\s]*|%20[^\"\s]*)", r"\1", body_html)
    return body_html


def build_articles() -> tuple[list[dict], list[dict]]:
    merged = json.loads((OUT / "news_items_merged.json").read_text())
    listing = {}
    for item in merged:
        listing[item["path"].rstrip("/").split("/")[-1]] = item
    harvested = {}
    for path in sorted(OUT.glob("article_*.json")):
        data = json.loads(path.read_text())
        harvested[data["slug"]] = data
    categories = category_rows(list(merged))
    category_names = {c["machine_name"] for c in categories}
    articles = []
    missing_bodies = []
    for slug, item in listing.items():
        data = harvested.get(slug)
        machine = item.get("category_machine") or ""
        if machine == "game_updates":
            machine = "game-updates"
        if machine not in category_names:
            category_names.add(machine)
            categories.append({
                "machine_name": machine,
                "title": item.get("category_title") or machine.replace("_", " ").replace("-", " ").title(),
                "description": item.get("category_description") or "",
            })
        publish = (item.get("publish_date") or "")
        record = {
            "slug": slug,
            "category": machine,
            "title": item.get("title") or "",
            "summary": item.get("description") or "",
            "publish_date": publish,
            "authors": [],
            "tags": [],
            "body_html": "",
            "related": [],
            "external_url": "",
            "banner": f"news/{slug}_banner.jpg" if (item.get("banner_url") or (harvested.get(slug, {}).get("masthead") or {}).get("banner_url")) else "",
        }
        if data:
            masthead = data.get("masthead") or {}
            if masthead:
                record["authors"] = masthead.get("authors") or []
                record["tags"] = masthead.get("tags") or []
                if masthead.get("publishDate"):
                    publish = masthead["publishDate"]
                    record["publish_date"] = publish
            body = data.get("body_html") or ""
            if body:
                record["body_html"] = rewrite_inline_images(
                    slug, body, data.get("inline_imgs") or [])
            else:
                missing_bodies.append(slug)
            related = []
            for rel in data.get("related") or []:
                rel_path = rel.get("path") or ""
                if not rel_path.startswith("/en-us/news/"):
                    continue
                rel_slug = rel_path.rstrip("/").split("/")[-1]
                if rel_slug not in listing:
                    continue
                rel_item = listing[rel_slug]
                rel_machine = (rel_item.get("category_machine") or "").replace("game_updates", "game-updates")
                related.append({
                    "title": rel.get("title") or rel_item.get("title") or "",
                    "path": f"/news/{rel_machine}/{rel_slug}/",
                    "card": f"news/{rel_slug}_card.jpg",
                })
            record["related"] = related[:6]
        articles.append(record)
    # patch-note classification + fallback banner images
    for record in articles:
        title = record["title"]
        record["is_patch_note"] = 1 if (
            title.startswith("League of Legends Patch") and title.endswith("Notes")) else 0
    articles.sort(key=lambda r: r["slug"])
    categories.sort(key=lambda r: r["machine_name"])
    if missing_bodies:
        print(f"[source] {len(missing_bodies)} articles without a harvested body: {missing_bodies[:6]}")
    return articles, categories


def build_external_items(articles: list[dict]) -> list[dict]:
    """External weblink cards shown on the news hub / category pages."""
    import hashlib
    merged = json.loads((OUT / "news_items_merged.json").read_text())
    externals = []
    hub = json.loads((OUT / "news_list.json").read_text())
    for item in hub:
        url = item.get("path") or ""
        if url.startswith("/en-us/news/"):
            continue
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        slug = f"link-{digest}"
        externals.append({
            "slug": slug,
            "title": item.get("title") or url,
            "summary": item.get("description") or "",
            "publish_date": item.get("publish_date") or "",
            "category": (item.get("category_machine") or "").replace("game_updates", "game-updates"),
            "external_url": url,
        })
    externals.sort(key=lambda r: r["title"])
    return externals


def main() -> int:
    champions = build_champions()
    articles, categories = build_articles()
    externals = build_external_items(articles)
    # category coverage check
    cat_names = {c["machine_name"] for c in categories}
    for record in articles:
        if record["category"] not in cat_names:
            raise SystemExit(f"unknown category for {record['slug']}: {record['category']}")
    source = {
        "meta": {
            "site": "league_of_legends",
            "upstream": "https://www.leagueoflegends.com/",
            "snapshot_date": "2026-09-22",
            "ddragon_version": "16.18.1",
        },
        "champions": champions,
        "categories": categories,
        "articles": articles,
        "external_links": externals,
    }
    DEST.write_text(json.dumps(source, indent=1, ensure_ascii=False, sort_keys=False))
    skin_total = sum(len(c["skins"]) for c in champions)
    ability_total = sum(len(c["abilities"]) for c in champions)
    patch_total = sum(a["is_patch_note"] for a in articles)
    print(f"[source] {len(champions)} champions, {skin_total} skins, "
          f"{ability_total} abilities")
    print(f"[source] {len(articles)} internal articles ({patch_total} patch notes), "
          f"{len(externals)} external cards, {len(categories)} categories")
    print(f"[source] written -> {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
