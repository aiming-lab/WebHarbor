#!/usr/bin/env python3
"""Harvest the imgur post catalog from the live site's own public API.

Stage 1 of the imgur mirror pipeline: collect post candidates from the same
api.imgur.com endpoints the live SPA renders from (hot/newest/user-submitted
feeds, top-of-week, per-tag feeds), deduplicate, and store the summaries.

Output: sites/imgur/scraped_data/catalog.json
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
CLIENT_ID = "d70305e7c3ac5c6"
BASE = "https://api.imgur.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

TAGS = [
    "funny", "aww", "current_events", "anime", "wallpaper", "art",
    "woodworking", "cat", "dog", "cute", "gaming", "wholesome",
    "science", "nature", "reaction", "tifu", "creative", "history",
    "food", "trendy", "comic", "pokemon", "space", "garden",
]


def get(cx: httpx.Client, path: str, params: dict) -> list | dict:
    for attempt in range(4):
        try:
            r = cx.get(BASE + path, params=params)
            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as error:
            print(f"  http error {error}; retry", flush=True)
            time.sleep(10)
    raise RuntimeError(f"failed after retries: {path} {params}")


def posts_params(section: str, page: int, sort: str, location: str) -> dict:
    params = {
        "client_id": CLIENT_ID,
        "filter[section]": f"eq:{section}",
        "include": "adtiles,adconfig,cover,tags,viral",
        "location": location,
        "page": page,
        "sort": sort,
    }
    return params


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cx = httpx.Client(timeout=40, headers={"User-Agent": UA, "Referer": "https://imgur.com/"})
    catalog: dict[str, dict] = {}

    def absorb(rows: list, source: str) -> None:
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            if row.get("is_ad"):
                continue
            pid = row["id"]
            if pid not in catalog:
                row["_sources"] = [source]
                catalog[pid] = row
            else:
                existing = catalog[pid]
                if source not in existing["_sources"]:
                    existing["_sources"].append(source)
                # keep the richest cover/tags seen across feeds
                if row.get("cover") and not existing.get("cover"):
                    existing["cover"] = row["cover"]
                if len(row.get("tags") or []) > len(existing.get("tags") or []):
                    existing["tags"] = row["tags"]

    # Most Viral / hot feed, newest ordering (the homepage default)
    for page in range(1, 13):
        rows = get(cx, "/post/v1/posts", posts_params("hot", page, "-time", "desktophome"))
        if not isinstance(rows, list) or not rows:
            break
        absorb([r for r in rows if isinstance(r, dict) and not r.get("is_ad")], f"hot-newest-p{page}")
        print(f"hot -time p{page}: +{len(rows)}", flush=True)

    # hot feed, popular ordering (the POPULAR sort)
    for page in range(1, 6):
        rows = get(cx, "/post/v1/posts", posts_params("hot", page, "-viral", "desktophome"))
        if not isinstance(rows, list) or not rows:
            break
        absorb([r for r in rows if isinstance(r, dict) and not r.get("is_ad")], f"hot-popular-p{page}")
        print(f"hot -viral p{page}: +{len(rows)}", flush=True)

    # User submitted feed (filter[section]=eq:new — captured from the live site's USER SUBMITTED view)
    for page in range(1, 6):
        rows = get(cx, "/post/v1/posts", posts_params("new", page, "-time", "desktophome"))
        if not isinstance(rows, list) or not rows:
            break
        absorb([r for r in rows if isinstance(r, dict) and not r.get("is_ad")], f"usersub-newest-p{page}")
        print(f"user_sub p{page}: +{len(rows)}", flush=True)

    # Top of week (the TOP gallery window)
    for page in range(1, 7):
        rows = get(cx, "/post/v1/posts", {
            "client_id": CLIENT_ID,
            "filter[section]": "eq:top",
            "filter[window]": "week",
            "include": "adconfig,cover,tags",
            "page": page,
            "sort": "viral",
        })
        if not isinstance(rows, list) or not rows:
            break
        absorb(rows, f"top-week-p{page}")
        print(f"top week p{page}: +{len(rows)}", flush=True)

    # Per-tag feeds (the /t/<tag> pages)
    tag_meta: dict[str, dict] = {}
    for tag in TAGS:
        for page in range(1, 3):
            blob = get(cx, f"/post/v1/posts/t/{tag}", {
                "client_id": CLIENT_ID,
                "filter[window]": "week",
                "include": "adtiles,adconfig,cover",
                "location": "desktoptag",
                "page": page,
                "sort": "-viral",
            })
            if not isinstance(blob, dict):
                break
            meta = {k: v for k, v in blob.items() if k != "posts"}
            tag_meta.setdefault(tag, meta)
            rows = [r for r in blob.get("posts", []) if isinstance(r, dict) and not r.get("is_ad")]
            if not rows:
                break
            absorb(rows, f"tag-{tag}-p{page}")
            if page == 1:
                for row in rows:
                    tags = row.get("tags") or []
                    if not any(t.get("tag") == tag for t in tags):
                        row.setdefault("_tags", []).append(tag)
        print(f"tag {tag}: catalog now {len(catalog)}", flush=True)

    (OUT / "tag_meta.json").write_text(json.dumps(tag_meta, ensure_ascii=False), encoding="utf-8")
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    print(f"catalog: {len(catalog)} unique posts -> catalog.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
