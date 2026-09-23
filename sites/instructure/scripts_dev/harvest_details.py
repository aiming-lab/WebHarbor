#!/usr/bin/env python3
"""Harvest every resource/press detail page (HTML) for seed construction.

Resumable: skips slugs whose HTML file already exists. Runs several
browser contexts in parallel threads.
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time

from playwright.sync_api import sync_playwright

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
    for name in LISTINGS:
        data = json.loads((OUT / f"listing_{name}.json").read_text(encoding="utf-8"))
        for row in data:
            href = row["href"].replace(BASE, "")
            if not href.startswith("/"):
                continue
            slug = href.strip("/").replace("/", "__")
            queue.append((slug, href))
    # dedupe
    seen = set()
    out = []
    for slug, href in queue:
        if slug in seen:
            continue
        seen.add(slug)
        out.append((slug, href))
    return out


def worker(queue: list[tuple[str, str]], idx: list[int], tid: int) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1200, "height": 800}, user_agent=UA)
        page = ctx.new_page()
        n = 0
        while idx[0] < len(queue):
            with idx_lock:
                i = idx[0]
                idx[0] += 1
            slug, href = queue[i]
            target = DET / f"{slug}.html"
            if target.exists() and target.stat().st_size > 50000:
                continue
            try:
                page.goto(BASE + href, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2200)
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(700)
                html = page.content()
                if len(html) > 50000:
                    target.write_text(html, encoding="utf-8")
                    n += 1
                    if n % 25 == 0:
                        print(f"[w{tid}] {n} saved (queue pos {i}/{len(queue)})", flush=True)
                else:
                    print(f"[w{tid}] SKIP small: {slug}", flush=True)
            except Exception as exc:
                print(f"[w{tid}] ERR {slug}: {str(exc)[:100]}", flush=True)
                time.sleep(1)
        browser.close()
    print(f"[w{tid}] done, saved {n}", flush=True)


idx_lock = threading.Lock()


def main() -> None:
    queue = build_queue()
    print(f"[queue] {len(queue)} detail pages", flush=True)
    nthreads = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    idx = [0]
    threads = [threading.Thread(target=worker, args=(queue, idx, t))
               for t in range(nthreads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("[all] complete", flush=True)


if __name__ == "__main__":
    main()
