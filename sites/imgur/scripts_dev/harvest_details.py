#!/usr/bin/env python3
"""Harvest post details and comments for the selected imgur catalog.

Stage 2b: for every post id in selection.json, fetch the live site's own
post/v1/posts/<id> (media, tags, account) and comment/v1/comments responses
and store them under scraped_data/details/<id>.json. Resumable — already
harvested ids are skipped.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
DETAILS = OUT / "details"
CLIENT_ID = "d70305e7c3ac5c6"
BASE = "https://api.imgur.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
MAX_COMMENTS = 40


def get(cx: httpx.Client, path: str, params: dict) -> object:
    for attempt in range(4):
        try:
            r = cx.get(BASE + path, params=params)
            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  429; waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as error:
            print(f"  http error {error}; retry", flush=True)
            time.sleep(10)
    raise RuntimeError(f"failed after retries: {path}")


def main() -> int:
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    DETAILS.mkdir(parents=True, exist_ok=True)
    cx = httpx.Client(timeout=40, headers={"User-Agent": UA, "Referer": "https://imgur.com/"})

    todo = [row["id"] for row in selection["selected"]
            if not (DETAILS / f"{row['id']}.json").exists()]
    print(f"harvesting {len(todo)} post details", flush=True)
    failures = []
    for n, pid in enumerate(todo, 1):
        try:
            post = get(cx, f"/post/v1/posts/{pid}", {
                "client_id": CLIENT_ID,
                "include": "media,tags,account,adconfig,promoted",
            })
            if not isinstance(post, dict) or not post.get("id"):
                failures.append((pid, "no-detail"))
                continue
            comments = get(cx, "/comment/v1/comments", {
                "client_id": CLIENT_ID,
                "filter[post]": f"eq:{pid}",
                "include": "account,adconfig",
                "per_page": MAX_COMMENTS,
                "sort": "best",
            })
            payload = {"post": post, "comments": comments}
            (DETAILS / f"{pid}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            if n % 25 == 0:
                print(f"  {n}/{len(todo)} done", flush=True)
            time.sleep(0.4)
        except Exception as error:
            failures.append((pid, str(error)))
            print(f"  FAILED {pid}: {error}", flush=True)

    print(f"done; failures={len(failures)}")
    for pid, why in failures:
        print(f"  {pid}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
