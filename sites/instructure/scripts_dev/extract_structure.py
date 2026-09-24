#!/usr/bin/env python3
"""Extract structured reference data from the captured upstream HTML files."""
from __future__ import annotations

import json
import pathlib
import re

from bs4 import BeautifulSoup

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"


def text_of(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def dump(name: str, data) -> None:
    (OUT / f"extract_{name}.json").write_text(
        json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[extract] {name}: {len(data) if isinstance(data, list) else 'ok'}")


def load(name: str) -> BeautifulSoup:
    return BeautifulSoup((OUT / f"{name}.html").read_text(encoding="utf-8"), "lxml")


def cards_from(soup: BeautifulSoup) -> list[dict]:
    """Generic card extractor: a link with an image + heading + meta text."""
    out = []
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href.startswith("/") or href.rstrip("/") in seen:
            continue
        img = a.select_one("img")
        if not img:
            continue
        heading = a.find(["h2", "h3", "h4", "h5"])
        if not heading:
            continue
        seen.add(href.rstrip("/"))
        row = {
            "href": href,
            "title": text_of(heading),
            "img": img.get("src") or img.get("data-src"),
            "alt": img.get("alt"),
            "text": text_of(a),
        }
        out.append(row)
    return out


def main() -> None:
    for page in ["resources", "case_studies", "ebooks", "videos", "blog",
                 "webinars", "research", "news", "events", "leadership",
                 "careers", "partners", "community"]:
        soup = load(page)
        dump(f"cards_{page}", cards_from(soup))


if __name__ == "__main__":
    main()
