#!/usr/bin/env python3
"""Pick and download extra real upstream images for the benchmark users' posts.

Stage 2e: the four benchmark accounts (alice_j, bob_c, carol_d, david_k)
exist only in the mirror, but their own posts carry REAL imgur imagery. This
script picks image posts from the harvested catalog that did NOT make the
main selection (fresh, safe, small static images), downloads their display
variants, and records the provenance for source_data.json.

Output: scraped_data/benchmark_posts.json
"""
from __future__ import annotations

import json
import pathlib
import sys

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
IMAGES = SITE / "static" / "images"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
MAX_ORIGINAL = 1_200_000
WANTED = 12


def main() -> int:
    catalog = json.loads((OUT / "catalog.json").read_text(encoding="utf-8"))
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    selected_ids = {row["id"] for row in selection["selected"]}

    ranked = sorted(catalog.values(), key=lambda p: p["id"])
    picked = []
    seen_titles = set()
    for post in ranked:
        if len(picked) >= WANTED:
            break
        if post["id"] in selected_ids:
            continue
        if post.get("is_mature") or post.get("is_pending"):
            continue
        cover = post.get("cover") or {}
        if cover.get("mime_type") not in ("image/jpeg", "image/png"):
            continue
        if (cover.get("size") or 0) > MAX_ORIGINAL:
            continue
        title = (post.get("title") or "").strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        picked.append(post)

    print(f"picked {len(picked)} image posts for benchmark users", flush=True)
    cx = httpx.Client(timeout=60, follow_redirects=True,
                      headers={"User-Agent": UA, "Referer": "https://imgur.com/"})

    def fetch(url: str) -> bytes | None:
        for attempt in range(3):
            try:
                r = cx.get(url)
                if r.status_code == 429:
                    import time
                    time.sleep(15 * (attempt + 1))
                    continue
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.content
            except httpx.HTTPError:
                continue
        return None

    records = []
    for post in picked:
        mid = post["cover_id"]
        feed_url = f"https://i.imgur.com/{mid}_d.webp?maxwidth=520"
        detail_url = f"https://i.imgur.com/{mid}h.jpg" if (post.get("cover") or {}).get("size", 0) > MAX_ORIGINAL else (post.get("cover") or {}).get("url")
        if not detail_url:
            detail_url = f"https://i.imgur.com/{mid}h.jpg"
        feed = fetch(feed_url)
        detail = fetch(detail_url)
        if not feed or not detail:
            print(f"  skip {mid}: download failed", flush=True)
            continue
        feed_path = IMAGES / "posts" / f"{mid}_feed.webp"
        detail_path = IMAGES / "posts" / f"{mid}_detail.jpg"
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        feed_path.write_bytes(feed)
        detail_path.write_bytes(detail)
        records.append({
            "media_id": mid,
            "upstream_post_id": post["id"],
            "upstream_url": post.get("url"),
            "feed_source": feed_url,
            "detail_source": detail_url,
            "feed_path": f"static/images/posts/{mid}_feed.webp",
            "detail_path": f"static/images/posts/{mid}_detail.jpg",
            "width": (post.get("cover") or {}).get("width"),
            "height": (post.get("cover") or {}).get("height"),
            "size": (post.get("cover") or {}).get("size"),
        })
        print(f"  saved {mid} ({len(feed)//1024}KB feed, {len(detail)//1024}KB detail)", flush=True)

    (OUT / "benchmark_posts.json").write_text(json.dumps(records, indent=1), encoding="utf-8")
    print(f"recorded {len(records)} benchmark post images", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
