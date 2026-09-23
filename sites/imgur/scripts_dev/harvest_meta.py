#!/usr/bin/env python3
"""Harvest post meta (accolades + author) for the selected catalog.

Stage 2d: the live gallery page calls post/v1/posts/<id>/meta?include=post,user,
accolades — this script captures the same payloads for the selected posts so
the mirror can render the real award ribbons.

Output: scraped_data/meta/<id>.json (resumable).
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
META = OUT / "meta"
CLIENT_ID = "d70305e7c3ac5c6"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


def get(cx: httpx.Client, path: str, params: dict) -> object:
    for attempt in range(4):
        try:
            r = cx.get("https://api.imgur.com" + path, params=params)
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
            time.sleep(8)
    return None


def main() -> int:
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    META.mkdir(parents=True, exist_ok=True)
    cx = httpx.Client(timeout=40, headers={"User-Agent": UA, "Referer": "https://imgur.com/"})
    todo = [row["id"] for row in selection["selected"]
            if not (META / f"{row['id']}.json").exists()]
    print(f"harvesting meta for {len(todo)} posts", flush=True)
    for n, pid in enumerate(todo, 1):
        payload = get(cx, f"/post/v1/posts/{pid}/meta", params={
            "client_id": CLIENT_ID, "include": "post,user,accolades"})
        if payload:
            (META / f"{pid}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        if n % 40 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(0.25)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
