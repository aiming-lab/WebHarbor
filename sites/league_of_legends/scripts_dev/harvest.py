#!/usr/bin/env python3
"""Harvest structured data from the live leagueoflegends.com site.

Drives a real Chromium via Playwright (per the clone-website skill), extracts
the Next.js __NEXT_DATA__ payload from each page, and stores per-page JSON
snapshots under scraped_data/. Image bytes are downloaded separately by
fetch_images.py.

Phases:
  roster     - champion list from the champions page (173 cards)
  champions  - per-champion detail pages (masthead, abilities, skins)
  news       - news hub listing (article cards, categories)
  articles   - per-article detail pages (masthead, body, related)
  static     - how-to-play / pbe / signup pages
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "scraped_data"
BASE = "https://www.leagueoflegends.com"


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("no __NEXT_DATA__ block")
    return json.loads(m.group(1))


def page_data(html: str) -> dict:
    d = next_data(html)
    return d["props"]["pageProps"]["page"]


def load_page(page, url: str, wait_ms: int = 6500, tries: int = 3) -> str:
    for attempt in range(tries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(wait_ms)
            html = page.content()
            if "__NEXT_DATA__" in html:
                return html
        except Exception as exc:  # noqa: BLE001
            print(f"  [retry {attempt+1}] {url}: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"failed to render: {url}")


# ---------------------------------------------------------------- phases

def harvest_roster() -> list[dict]:
    html = (OUT / "champions.html").read_text()
    pat = re.compile(
        r'<a role="button" aria-label="([^"]+)" href="(/en-us/champions/[a-z0-9-]+/)"[^>]*>.*?'
        r'<img src="([^"]+)"', re.S)
    cards = []
    for name, href, img in pat.findall(html):
        cards.append({"name": name, "slug": href.strip("/").split("/")[-1], "portrait_url": img})
    cards = sorted({c["slug"]: c for c in cards}.values(), key=lambda c: c["name"].lower())
    (OUT / "roster.json").write_text(json.dumps(cards, indent=1))
    print(f"[roster] {len(cards)} champions")
    return cards


def harvest_one_chromium(slugs: list[str], worker: int) -> list[str]:
    done: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        page = ctx.new_page()
        for slug in slugs:
            dest = OUT / f"champion_{slug}.json"
            if dest.exists():
                done.append(slug)
                continue
            try:
                html = load_page(page, f"{BASE}/en-us/champions/{slug}/")
                data = page_data(html)
                blades = data.get("blades", [])
                masthead = next((b for b in blades if b.get("type") == "characterMasthead"), None)
                icon_tab = next((b for b in blades if b.get("type") == "iconTab"), None)
                skins = next((b for b in blades if b.get("type") == "landingMediaCarousel"), None)
                record = {
                    "slug": slug,
                    "url": data.get("url"),
                    "masthead": None,
                    "abilities": [],
                    "skins": [],
                }
                if masthead:
                    backdrop = (masthead.get("backdrop") or {}).get("background") or {}
                    record["masthead"] = {
                        "title": masthead.get("title"),
                        "subtitle": masthead.get("subtitle"),
                        "roles": [r.get("name") for r in ((masthead.get("role") or {}).get("roles") or [])],
                        "difficulty": (masthead.get("difficulty") or {}).get("name"),
                        "difficulty_value": (masthead.get("difficulty") or {}).get("value"),
                        "description": (masthead.get("description") or {}).get("body"),
                        "backdrop_url": backdrop.get("url"),
                    }
                if icon_tab:
                    for group in icon_tab.get("groups", []):
                        content = group.get("content") or {}
                        media = content.get("media") or {}
                        thumb = media.get("thumbnail") or {}
                        gthumb = group.get("thumbnail") or {}
                        record["abilities"].append({
                            "name": group.get("label"),
                            "slot": content.get("subtitle"),
                            "description": (content.get("description") or {}).get("body"),
                            "icon_url": gthumb.get("url"),
                            "poster_url": thumb.get("url"),
                        })
                if skins:
                    for group in skins.get("groups", []):
                        thumb = group.get("thumbnail") or {}
                        content = (group.get("content") or {}).get("media") or {}
                        record["skins"].append({
                            "name": group.get("label"),
                            "splash_url": thumb.get("url") or content.get("url"),
                        })
                dest.write_text(json.dumps(record, indent=1))
                done.append(slug)
                print(f"  [w{worker}] {slug}: {len(record['abilities'])} abilities, {len(record['skins'])} skins", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  [w{worker}] FAIL {slug}: {str(exc)[:160]}", flush=True)
        browser.close()
    return done


def harvest_champions(cards: list[dict], workers: int = 6) -> None:
    slugs = [c["slug"] for c in cards]
    chunks: list[list[str]] = [[] for _ in range(workers)]
    for i, slug in enumerate(slugs):
        chunks[i % workers].append(slug)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda pair: harvest_one_chromium(pair[1], pair[0] + 1), enumerate(chunks)))
    total = sum(len(r) for r in results)
    print(f"[champions] harvested {total}/{len(slugs)} champion pages")


def harvest_news() -> list[dict]:
    html = (OUT / "news.html").read_text()
    data = page_data(html)
    grid = next((b for b in data.get("blades", []) if b.get("type") == "articleCardGrid"), None)
    items = []
    for it in (grid or {}).get("items", []):
        action = (it.get("action") or {}).get("payload") or {}
        analytics = it.get("analytics") or {}
        category = it.get("category") or {}
        items.append({
            "title": it.get("title"),
            "path": action.get("url"),
            "category_machine": category.get("machineName"),
            "category_title": category.get("title"),
            "category_description": category.get("description"),
            "description": (it.get("description") or {}).get("body"),
            "banner_url": (it.get("imageMedia") or it.get("media") or {}).get("url"),
            "publish_date": analytics.get("publishDate"),
        })
    # rendered card image URLs (with the CDN size params the live grid requests)
    card_imgs = re.findall(r'data-testid="article-card"[^>]*>.*?<img src="([^"]+)"', html, re.S)
    items_path = {}
    for m in re.finditer(r'<a[^>]*href="(/en-us/news/[^"]+)"[^>]*>.*?<img src="([^"]+)"', html, re.S):
        items_path[m.group(1)] = m.group(2)
    for it in items:
        rendered = items_path.get(it["path"] or "")
        if rendered:
            it["card_img_url"] = rendered
    (OUT / "news_list.json").write_text(json.dumps(items, indent=1))
    print(f"[news] {len(items)} article cards on the hub")
    return items


def harvest_one_articles(paths: list[str], worker: int) -> list[str]:
    done: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        page = ctx.new_page()
        for path in paths:
            slug = path.rstrip("/").split("/")[-1]
            dest = OUT / f"article_{slug}.json"
            if dest.exists():
                done.append(slug)
                continue
            try:
                html = load_page(page, f"{BASE}{path}")
                data = page_data(html)
                blades = data.get("blades", [])
                masthead = next((b for b in blades if b.get("type") == "articleMasthead"), None)
                body_blade = next((b for b in blades if b.get("type") in ("patchNotesRichText", "articleRichText", "richText")), None)
                related = next((b for b in blades if b.get("type") == "articleCardCarousel"), None)
                record = {
                    "slug": slug,
                    "path": path,
                    "url": data.get("url"),
                    "title": data.get("title"),
                    "displayedPublishDate": data.get("displayedPublishDate"),
                    "masthead": None,
                    "body_html": None,
                    "related": [],
                }
                if masthead:
                    banner = (masthead.get("banner") or {})
                    record["masthead"] = {
                        "title": masthead.get("title"),
                        "description": (masthead.get("description") or {}).get("body"),
                        "publishDate": masthead.get("publishDate"),
                        "category_machine": (masthead.get("category") or {}).get("machineName"),
                        "category_title": (masthead.get("category") or {}).get("title"),
                        "tags": [t.get("title") for t in (masthead.get("tags") or [])],
                        "authors": [a.get("name") for a in (masthead.get("authors") or [])],
                        "banner_url": (banner.get("background") or banner or {}).get("url") if isinstance(banner, dict) else None,
                    }
                if body_blade:
                    record["body_html"] = (body_blade.get("richText") or {}).get("body")
                if related:
                    for it in related.get("items", []):
                        action = (it.get("action") or {}).get("payload") or {}
                        record["related"].append({
                            "title": it.get("title"),
                            "path": action.get("url"),
                            "banner_url": (it.get("imageMedia") or it.get("media") or {}).get("url"),
                        })
                # inline images actually rendered in the body
                if record["body_html"]:
                    record["inline_imgs"] = sorted(set(re.findall(r'<img[^>]*src="([^"]+)"', record["body_html"])))
                dest.write_text(json.dumps(record, indent=1))
                done.append(slug)
                print(f"  [w{worker}] article {slug}: body={len(record['body_html'] or '')}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  [w{worker}] FAIL {path}: {str(exc)[:160]}", flush=True)
        browser.close()
    return done


def harvest_articles(items: list[dict], workers: int = 6, limit: int | None = None) -> None:
    paths = []
    for it in items:
        path = it.get("path")
        if path and path.startswith("/en-us/news/"):
            paths.append(path if path.endswith("/") else path + "/")
    paths = sorted(set(paths))
    if limit:
        paths = paths[:limit]
    chunks: list[list[str]] = [[] for _ in range(workers)]
    for i, path in enumerate(paths):
        chunks[i % workers].append(path)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda pair: harvest_one_articles(pair[1], pair[0] + 1), enumerate(chunks)))
    total = sum(len(r) for r in results)
    print(f"[articles] harvested {total}/{len(paths)} article pages")


def harvest_static_pages() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        page = ctx.new_page()
        for name, url in [
            ("how_to_play", f"{BASE}/en-us/how-to-play/"),
            ("pbe", f"{BASE}/en-us/pbe/"),
            ("signup", f"{BASE}/en-us/signup/"),
            ("classic", f"{BASE}/en-us/classic/"),
        ]:
            try:
                html = load_page(page, url)
                (OUT / f"{name}.html").write_text(html)
                try:
                    data = page_data(html)
                    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1))
                except Exception as exc:  # noqa: BLE001
                    print(f"  [{name}] no page data: {str(exc)[:100]}", flush=True)
                print(f"  [{name}] captured", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{name}] FAIL: {str(exc)[:160]}", flush=True)
        browser.close()


def _merged_article_items() -> list[dict]:
    merged = OUT / "news_items_merged.json"
    if merged.exists():
        return json.loads(merged.read_text())
    return json.loads((OUT / "news_list.json").read_text())


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    OUT.mkdir(exist_ok=True)
    if phase in ("all", "roster"):
        cards = harvest_roster()
    else:
        cards = json.loads((OUT / "roster.json").read_text())
    if phase in ("all", "champions"):
        harvest_champions(cards)
    if phase in ("all", "news"):
        items = harvest_news()
    else:
        items = _merged_article_items()
    if phase in ("all", "articles"):
        limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
        harvest_articles(items, limit=limit)
    if phase in ("all", "static"):
        harvest_static_pages()
    print("[harvest] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
