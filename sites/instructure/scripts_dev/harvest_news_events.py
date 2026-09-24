#!/usr/bin/env python3
"""Harvest news, press releases, events listings with their real markup."""
from __future__ import annotations

import json
import pathlib
import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
BASE = "https://www.instructure.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def parse_news(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for li in soup.select("li.in-the-news-item"):
        a = li.select_one("a[href]")
        art = li.select_one("article")
        date = li.select_one("time")
        title = li.select_one("h3")
        outlet = li.select_one(".field--name-field-news-outlet")
        tags = li.select_one(".field--name-field-tags-9")
        spokes = li.select_one(".field--name-field-spokesperson")
        rows.append({
            "href": a.get("href") if a else "",
            "about": art.get("about") if art else "",
            "date": clean(date.get_text() if date else ""),
            "datetime": date.get("datetime") if date else "",
            "title": clean(title.get_text() if title else ""),
            "outlet": clean(outlet.get_text() if outlet else ""),
            "region": clean(tags.get_text() if tags else ""),
            "spokesperson": clean(spokes.get_text() if spokes else ""),
        })
    return rows


def parse_events(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tile in soup.select(".events-tile"):
        art = tile.select_one("article")
        img = tile.select_one("img")
        etype = tile.select_one(".field--name-field-event-type")
        edate = tile.select_one(".event-date")
        heading = tile.select_one("h5")
        link = tile.select_one("a.event-link")
        rows.append({
            "about": art.get("about") if art else "",
            "img": img.get("src") if img else None,
            "event_type": clean(etype.get_text() if etype else ""),
            "date": clean(edate.get_text() if edate else ""),
            "title": clean(heading.get_text() if heading else ""),
            "href": link.get("href") if link else "",
        })
    return rows


def parse_generic_feed(html: str) -> list[dict]:
    """blog-page-item feeds (press releases etc)."""
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for li in soup.select("li.blog-page-item"):
        a = li.select_one(".blog-list-item-title a")
        img = li.select_one("img")
        rtype = li.select_one(".resource-type")
        body = li.select_one(".views-field-nothing-1 .field-content")
        rows.append({
            "href": a.get("href") if a else "",
            "title": clean(a.get_text() if a else ""),
            "type": clean(rtype.get_text() if rtype else ""),
            "img": img.get("src") if img else None,
            "snippet": clean(body.get_text() if body else ""),
        })
    return rows


def fetch(page, url: str, wait: int = 5000):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(wait)
    page.mouse.wheel(0, 1200)
    page.wait_for_timeout(1200)
    return page.content()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, user_agent=UA)
        page = ctx.new_page()

        news, seen = [], set()
        for pg in range(4):
            html = fetch(page, BASE + "/news" + (f"?page={pg}" if pg else ""))
            for r in parse_news(html):
                if r["title"] in seen:
                    continue
                seen.add(r["title"])
                news.append(r)
            if not parse_news(html):
                break
        print(f"[news] {len(news)}")

        prs, seen = [], set()
        for pg in range(6):
            html = fetch(page, BASE + "/news/public-relations" + (f"?page={pg}" if pg else ""))
            rows = parse_generic_feed(html)
            for r in rows:
                if r["title"] in seen:
                    continue
                seen.add(r["title"])
                prs.append(r)
            if not rows:
                break
        print(f"[press] {len(prs)}")

        events, seen = [], set()
        for pg in range(6):
            html = fetch(page, BASE + "/events" + (f"?page={pg}" if pg else ""))
            rows = parse_events(html)
            fresh = 0
            for r in rows:
                if r["about"] in seen:
                    continue
                seen.add(r["about"])
                events.append(r)
                fresh += 1
            if not fresh:
                break
        print(f"[events] {len(events)}")

        browser.close()

    (OUT / "listing_news.json").write_text(json.dumps(news, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "listing_press.json").write_text(json.dumps(prs, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "listing_events.json").write_text(json.dumps(events, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
