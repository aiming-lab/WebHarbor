#!/usr/bin/env python3
"""Harvest paginated hub listings (case studies, ebooks, blog, ...) into JSON."""
from __future__ import annotations

import json
import pathlib
import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
BASE = "https://www.instructure.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# name -> (path, max_pages)
HUBS = {
    "case_studies": ("/resources/case-studies", 9),
    "ebooks": ("/resources/ebooks", 5),
    "videos": ("/resources/videos", 4),
    "blog": ("/resources/blog", 6),
    "webinars": ("/resources/webinars", 4),
    "research": ("/resources/research", 3),
    "news": ("/news", 4),
    "events": ("/events", 3),
    "podcast": ("/resources/podcast", 2),
    "infographic": ("/resources/infographic", 2),
    "product_overviews": ("/resources/product-overviews", 3),
}


def parse_items(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for li in soup.select("li.blog-page-item"):
        a_title = li.select_one(".blog-list-item-title a")
        a_media = li.select_one(".views-field-field-media a")
        img = li.select_one("img")
        rtype = li.select_one(".resource-type")
        body = li.select_one(".views-field-nothing-1 .field-content")
        date = li.select_one(".views-field-created, .views-field-field-date")
        row = {
            "href": (a_title or {}).get("href", "") if a_title else "",
            "title": a_title.get_text(strip=True) if a_title else "",
            "type": rtype.get_text(strip=True) if rtype else "",
            "img": (img.get("src") if img is not None else None),
            "alt": (img.get("alt") if img is not None else None),
            "snippet": re.sub(r"\s+", " ", body.get_text(" ", strip=True)) if body else "",
            "date": re.sub(r"\s+", " ", date.get_text(" ", strip=True)) if date else "",
        }
        if row["title"] and row["href"]:
            rows.append(row)
    # events page uses different markup
    if not rows:
        for li in soup.select("li.views-row, .events-row, article"):
            a = li.select_one("a[href]")
            if not a:
                continue
            rows.append({
                "href": a.get("href", ""),
                "title": re.sub(r"\s+", " ", li.get_text(" ", strip=True))[:200],
                "type": "event",
                "img": None, "alt": None, "snippet": "", "date": "",
            })
    return rows


def main() -> None:
    hubs = list(HUBS.items())
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, user_agent=UA)
        page = ctx.new_page()
        all_items: dict[str, list] = {}
        for name, (path, max_pages) in hubs:
            items: list[dict] = []
            seen = set()
            for pg in range(max_pages):
                url = BASE + path + (f"?page={pg}" if pg else "")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4500)
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1200)
                    html = page.content()
                    rows = parse_items(html)
                except Exception as exc:
                    print(f"  [{name} p{pg}] ERROR {exc}", flush=True)
                    break
                fresh = [r for r in rows if r["href"] not in seen]
                for r in fresh:
                    seen.add(r["href"])
                items.extend(fresh)
                print(f"  [{name} p{pg}] +{len(fresh)} (total {len(items)})", flush=True)
                if not fresh:
                    break
                time.sleep(1.0)
            all_items[name] = items
        browser.close()
    for name, items in all_items.items():
        (OUT / f"listing_{name}.json").write_text(
            json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"[listing] {name}: {len(items)}")


if __name__ == "__main__":
    main()
