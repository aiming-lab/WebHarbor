#!/usr/bin/env python3
"""Summarize main-content sections of captured pages for mirror design reference."""
from __future__ import annotations

import json
import pathlib
import re

from bs4 import BeautifulSoup

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main_content(name: str) -> dict:
    soup = BeautifulSoup((OUT / f"{name}.html").read_text(encoding="utf-8"), "lxml")
    art = soup.select_one("article#asset, main article, #asset")
    root = art if art else soup.select_one("main")
    out = {"sections": [], "links": [], "images": []}
    if not root:
        return out
    for el in root.select("h1, h2, h3, h4, h5"):
        out["sections"].append({"tag": el.name, "text": clean(el.get_text())})
    for img in root.select("img"):
        src = img.get("src") or img.get("data-src")
        if src and not src.endswith((".svg", "Clear.gif")) and "logo" not in (img.get("alt") or "").lower():
            out["images"].append({"src": src, "alt": img.get("alt")})
    for a in root.select("a[href]"):
        href = a.get("href", "")
        text = clean(a.get_text())
        if href.startswith("/") and text and len(text) > 2:
            out["links"].append({"href": href, "text": text[:80]})
    return out


def main() -> None:
    summary = {}
    for f in sorted(OUT.glob("*.html")):
        name = f.stem
        if name in {"home_full", "search_canvas", "press"}:
            continue
        summary[name] = main_content(name)
    (OUT / "page_sections.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, data in summary.items():
        hs = [s["text"] for s in data["sections"] if s["tag"] in ("h1", "h2")][:14]
        print(f"== {name}: {len(data['sections'])} headings, {len(data['images'])} imgs, {len(data['links'])} links")
        for h in hs[:10]:
            print("   ", h[:90])


if __name__ == "__main__":
    main()
