#!/usr/bin/env python3
"""Stage 7: sweep upstream collection pages to complete the quick-view data.

Every collection card embeds a quick-view payload (title, price, compare-at
price, percentage off, subheading, specs, image). Related-carousels on PDPs
only cover part of the catalog, so the main listing pages are swept here to
complete scraped_data/quickview_data.json for every visible product that
upstream actually serves one for.

Saves HTML under scraped_data/collection_html/ and merges the parsed
quick-view payloads back into scraped_data/quickview_data.json.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_pdps import parse_quickviews  # noqa: E402

SITE = "https://macyswineshop.com"
BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

COLLECTIONS = {
    "all-wine": 10,
    "shop-all-wine-sets": 10,
    "new-arrivals": 4,
    "best-sellers": 4,
    "on-sale-and-clearance": 4,
    "red-wine": 4,
    "white-wine": 4,
    "rose-wine": 4,
    "sparkling-wine": 4,
    "award-winners": 3,
    "customer-favorites": 3,
    "sommeliers-choice": 3,
    "90-rated-wine-under-20": 3,
    "wine-sets-under-50": 3,
    "wine-sets-under-100": 3,
    "luxe-gifts": 3,
    "martha-stewart-wine-collection": 3,
    "non-alcoholic-wines": 2,
    "ready-to-drink-cocktails": 2,
    "3-bottle-wine-sets": 3,
    "6-bottle-wine-sets": 3,
    "12-bottle-wine-sets": 3,
}


def main() -> None:
    html_dir = OUT / "collection_html"
    html_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=60) as cx:
        for handle, max_pages in COLLECTIONS.items():
            for page in range(1, max_pages + 1):
                dest = html_dir / f"{handle}__p{page}.html"
                if dest.exists():
                    continue
                url = f"{SITE}/collections/{handle}?page={page}"
                for attempt in range(4):
                    try:
                        r = cx.get(url)
                        if r.status_code == 200:
                            dest.write_text(r.text)
                            break
                        if r.status_code == 404:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(1.5 * (attempt + 1))
                time.sleep(0.25)
            print(f"[cards] {handle} swept")

    quickview = json.loads((OUT / "quickview_data.json").read_text())
    before = len(quickview)
    for path in sorted(html_dir.glob("*.html")):
        html = path.read_text(encoding="utf-8", errors="replace")
        for qv in parse_quickviews(html):
            url = qv.get("url") or ""
            h = url.rstrip("/").split("/")[-1]
            if h and h not in quickview:
                quickview[h] = qv
    (OUT / "quickview_data.json").write_text(json.dumps(quickview, ensure_ascii=False, indent=1))
    print(f"[cards] quickview entries: {before} -> {len(quickview)}")


if __name__ == "__main__":
    main()
