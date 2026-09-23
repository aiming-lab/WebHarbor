#!/usr/bin/env python3
"""Stage 2: capture every visible product's detail page HTML from upstream.

The Shopify theme renders the whole PDP server-side, so plain HTTP GETs
capture the real DOM the browser sees (including the per-variant case
contents of pack products, awards, and the quick-view payloads of the
"You May Also Like" carousel).

Saves each page under scraped_data/pdp_html/<handle>.html (gitignored).
Resumable: existing files are kept.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

SITE = "https://macyswineshop.com"
BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def main() -> None:
    html_dir = OUT / "pdp_html"
    html_dir.mkdir(parents=True, exist_ok=True)
    products = json.loads((OUT / "products_visible.json").read_text())
    handles = [p["handle"] for p in products]
    todo = [h for h in handles if not (html_dir / f"{h}.html").exists()]
    print(f"[pdp] {len(handles)} products, {len(todo)} to fetch")
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=60) as cx:
        for i, handle in enumerate(todo):
            last_err = None
            for attempt in range(4):
                try:
                    r = cx.get(f"{SITE}/products/{handle}")
                    if r.status_code == 200:
                        (html_dir / f"{handle}.html").write_text(r.text)
                        break
                    last_err = f"status {r.status_code}"
                except httpx.HTTPError as exc:
                    last_err = str(exc)
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"[pdp] FAILED {handle}: {last_err}", file=sys.stderr)
            if (i + 1) % 50 == 0:
                print(f"[pdp] {i + 1}/{len(todo)} fetched")
            time.sleep(0.25)
    missing = [h for h in handles if not (html_dir / f"{h}.html").exists()]
    print(f"[pdp] done; missing={len(missing)}")
    if missing:
        print("missing:", missing[:10], file=sys.stderr)


if __name__ == "__main__":
    main()
