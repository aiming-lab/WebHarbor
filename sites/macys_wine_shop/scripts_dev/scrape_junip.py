#!/usr/bin/env python3
"""Stage 3: capture Junip review summaries and review bodies per product.

The storefront renders ratings through Junip's widget API (public store key
embedded in the live pages). Both the summary (rating average, count,
distribution, recommendation percentage) and up to 50 newest review bodies
are fetched per visible product.

Saves scraped_data/junip/<remote_id>.json. Resumable.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
STORE_KEY = "HbeZpMp5UCb32BFDwKG5qJ3Y"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/153.0.8010.12 Safari/537.36"),
    "Referer": "https://macyswineshop.com/",
    "Accept": "application/json",
    "junip-store-key": STORE_KEY,
    "content-type": "application/json",
}


def fetch(cx: httpx.Client, url: str) -> dict | None:
    for attempt in range(4):
        try:
            r = cx.get(url, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return {}
            print(f"  [warn] {url} -> {r.status_code}")
            return None
        except httpx.HTTPError as exc:
            print(f"  [retry] {exc}")
            time.sleep(2 * (attempt + 1))
    return None


def main() -> None:
    junip_dir = OUT / "junip"
    junip_dir.mkdir(parents=True, exist_ok=True)
    products = json.loads((OUT / "products_visible.json").read_text())
    with httpx.Client(headers=HEADERS) as cx:
        for i, p in enumerate(products):
            rid = p["id"]
            out = junip_dir / f"{rid}.json"
            if out.exists():
                continue
            summary = fetch(cx, f"https://apid.juniphq.com/en/v2/products/remote/{rid}?v={STORE_KEY}")
            reviews = fetch(cx, (
                f"https://apid.juniphq.com/en/v2/products/remote/{rid}/reviews"
                f"?page_size=50&sort_field=created_at&sort_order=desc&v={STORE_KEY}"))
            if summary is None or reviews is None:
                print(f"[junip] FAILED {p['handle']}")
                continue
            data = {
                "remote_id": rid,
                "handle": p["handle"],
                "title": p["title"],
                "summary": (summary or {}).get("data"),
                "reviews": (reviews or {}).get("data", []),
            }
            out.write_text(json.dumps(data, ensure_ascii=False))
            if (i + 1) % 50 == 0:
                print(f"[junip] {i + 1}/{len(products)}")
            time.sleep(0.3)
    print("[junip] done")


if __name__ == "__main__":
    main()
