#!/usr/bin/env python3
"""Collect every real upstream image URL referenced by the captured pages/listings."""
from __future__ import annotations

import json
import pathlib
import re
from urllib.parse import unquote

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
BASE = "https://www.instructure.com"

EXCLUDE_PATTERNS = [
    r"Clear\.gif", r"cookielaw\.org", r"googleads", r"doubleclick", r"clarity\.ms",
    r"facebook\.net", r"twitter\.com/i/adsct", r"analytics\.twitter", r"mountain\.com",
    r"company-target", r"addtoany", r"qualified\.com", r"adobedc", r"wistia\.com",
    r"bat\.bing", r"px\.mountain", r"googletagmanager", r"rlcdn", r"usbrowserspeed",
    r"\.svg$", r"/libraries/", r"logo-footer", r"data:image",
]

urls: dict[str, str] = {}   # url -> note


def add(url: str, note: str) -> None:
    if not url:
        return
    url = url.split(" ")[0]
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        url = BASE + url
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, url, re.I):
            return
    if not url.startswith(BASE):
        return
    if url not in urls:
        urls[url] = note


# 1. listings: resource thumbnails + event tiles
for name in ["case_studies", "ebooks", "videos", "blog", "webinars", "research",
             "podcast", "infographic", "product_overviews", "news", "press"]:
    data = json.loads((OUT / f"listing_{name}.json").read_text(encoding="utf-8"))
    for row in data:
        add(row.get("img"), f"listing:{name}")

# 2. reference json: leaders, hero slides
ref = json.loads((OUT / "source_reference.json").read_text(encoding="utf-8"))
for slide in ref.get("home", {}).get("hero_slides", []):
    add(slide.get("img"), "home:hero")
for leader in ref.get("leaders", []):
    add(leader.get("card_img"), "leader:card")
    add(leader.get("modal_img"), "leader:modal")

# 3. all captured page HTMLs
for html_file in list(OUT.glob("*.html")) + list((OUT / "details").glob("*.html")):
    text = html_file.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r'(?:src|data-src|srcset)="([^"]+)"', text):
        for part in m.group(1).split(","):
            u = part.strip().split(" ")[0]
            add(u, f"html:{html_file.name}")

print(f"collected {len(urls)} unique upstream image URLs")
(OUT / "image_urls.json").write_text(
    json.dumps([{"url": u, "note": n} for u, n in sorted(urls.items())],
               indent=1, ensure_ascii=False), encoding="utf-8")
total = 0
for u in urls:
    if "/styles/" in u or "/image/" in u:
        total += 1
print("instructure.com media URLs:", sum(1 for u in urls if "/image/" in u or "/styles/" in u))
