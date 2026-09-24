#!/usr/bin/env python3
"""Harvest every resource/press detail page (HTML) via plain HTTP (server-rendered).

Resumable: skips slugs whose HTML file already exists.
"""
from __future__ import annotations

import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
DET = OUT / "detail_pages"
DET.mkdir(exist_ok=True)
BASE = "https://www.instructure.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

LISTINGS = ["case_studies", "ebooks", "videos", "blog", "webinars", "research",
            "podcast", "infographic", "product_overviews", "press"]


def build_queue() -> list[tuple[str, str]]:
    queue: list[tuple[str, str]] = []
    seen = set()
    for name in LISTINGS:
        data = json.loads((OUT / f"listing_{name}.json").read_text(encoding="utf-8"))
        for row in data:
            href = row["href"].replace(BASE, "")
            if not href.startswith("/"):
                continue
            slug = href.strip("/").replace("/", "__")
            if slug in seen:
                continue
            seen.add(slug)
            queue.append((slug, href))
    return queue


def fetch_one(client: httpx.Client, item: tuple[str, str]) -> None:
    slug, href = item
    target = DET / f"{slug}.html"
    if target.exists() and target.stat().st_size > 40000:
        return
    for attempt in range(3):
        try:
            r = client.get(BASE + href)
            if r.status_code == 200 and len(r.content) > 40000:
                target.write_bytes(r.content)
                return
            if r.status_code in (429, 502, 503):
                import time
                time.sleep(2 + attempt * 3)
                continue
            # non-200 (e.g., 404) — record nothing
            print(f"  [http {r.status_code}] {slug}", flush=True)
            return
        except httpx.HTTPError as exc:
            print(f"  [err] {slug}: {str(exc)[:60]}", flush=True)
            import time
            time.sleep(2)


def main() -> None:
    queue = build_queue()
    print(f"[queue] {len(queue)} detail pages", flush=True)
    done = 0
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True,
                      timeout=30) as client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(lambda item: fetch_one(client, item), queue):
                done += 1
                if done % 50 == 0:
                    print(f"[progress] {done}/{len(queue)}", flush=True)
    count = len(list(DET.glob("*.html")))
    print(f"[all] complete, files: {count}", flush=True)


if __name__ == "__main__":
    main()
