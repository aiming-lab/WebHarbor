#!/usr/bin/env python3
"""Harvest imgur member profiles, meme templates, trophies and default avatars.

Stage 2c: fetch account/v1 member data (bio, reputation, trophies) for every
account the mirror references (post authors and commenters), fetch the
memegen default templates, and download the remaining chrome (default
avatars for registration). Resumable: members.json accumulates.

Outputs (all under scraped_data/):
  members.json        — username -> account payload (incl. trophies)
  meme_templates.json — the imgur memegen default template set
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
IMAGES = SITE / "static" / "images"
CLIENT_ID = "d70305e7c3ac5c6"
BASE = "https://api.imgur.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


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
            time.sleep(8)
    return None


def download(cx: httpx.Client, url: str, path: pathlib.Path) -> bool:
    if path.exists() and path.stat().st_size > 0:
        return True
    for attempt in range(3):
        try:
            r = cx.get(url)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            if r.status_code == 404:
                print(f"  MISSING {url[:90]}", flush=True)
                return False
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            return True
        except httpx.HTTPError as error:
            print(f"  http error {error}; retry {url[:90]}", flush=True)
            time.sleep(8)
    return False


def seen_usernames() -> list[str]:
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    details_dir = OUT / "details"
    names: set[str] = set()
    for row in selection["selected"]:
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        account = payload["post"].get("account") or {}
        if account.get("username"):
            names.add(account["username"])
        blob = payload.get("comments") or {}
        for comment in blob.get("data") or []:
            for target in [comment] + (comment.get("comments") or []):
                acc = target.get("account") or {}
                if acc.get("username"):
                    names.add(acc["username"])
    return sorted(names)


def main() -> int:
    names = seen_usernames()
    members_path = OUT / "members.json"
    member_data: dict[str, dict] = {}
    if members_path.exists():
        member_data = json.loads(members_path.read_text(encoding="utf-8"))
    todo = [n for n in names if n not in member_data]
    print(f"accounts seen: {len(names)}; already harvested: {len(member_data)}; todo: {len(todo)}", flush=True)

    cx = httpx.Client(timeout=40, headers={"User-Agent": UA, "Referer": "https://imgur.com/"})
    for n, username in enumerate(todo, 1):
        payload = get(cx, f"/account/v1/accounts/{username}", params={
            "client_id": CLIENT_ID, "include": "trophies,medallions,follow,seo"})
        if isinstance(payload, dict) and payload.get("id"):
            member_data[username] = payload
        if n % 25 == 0 or n == len(todo):
            members_path.write_text(json.dumps(member_data, ensure_ascii=False), encoding="utf-8")
            print(f"  members {n}/{len(todo)}", flush=True)
        time.sleep(0.25)

    members_path.write_text(json.dumps(member_data, ensure_ascii=False), encoding="utf-8")

    # trophy images hosted on i.imgur.com
    trophy_images: set[str] = set()
    for payload in member_data.values():
        for trophy in payload.get("trophies") or []:
            image = trophy.get("image_url") or ""
            if image.startswith("https://i.imgur.com/"):
                trophy_images.add(image.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    print(f"downloading {len(trophy_images)} member trophy images", flush=True)
    for mid in sorted(trophy_images):
        download(cx, f"https://i.imgur.com/{mid}.png", IMAGES / "trophies" / f"{mid}.png")

    # meme templates from imgur's own memegen defaults
    templates = get(cx, "/3/memegen/defaults", params={"client_id": CLIENT_ID})
    templates = templates.get("data") if isinstance(templates, dict) else []
    print(f"memegen templates: {len(templates)}", flush=True)
    (OUT / "meme_templates.json").write_text(json.dumps(templates, ensure_ascii=False), encoding="utf-8")
    for template in templates:
        link = template.get("link") or ""
        if link.startswith("https://i.imgur.com/"):
            ext = link.rsplit(".", 1)[-1]
            download(cx, link, IMAGES / "meme_templates" / f"{template['id']}.{ext}")
    print("templates downloaded", flush=True)

    # default avatars for the register flow: six real imgur flavor avatars
    avatars: dict[str, str] = {}
    details_dir = OUT / "details"
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    for row in selection["selected"]:
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        account = payload["post"].get("account") or {}
        if account.get("username") and account.get("avatar"):
            avatars.setdefault(account["username"], account["avatar"])
    names_order = [u for u in sorted(avatars) if u in member_data]
    chosen = [avatars[u] for u in names_order[:6]]
    defaults = ["default_alien", "default_banana", "default_doge", "default_robot", "default_ufo", "default_yarn"]
    for name, url in zip(defaults, chosen):
        download(cx, url, IMAGES / "avatars" / f"{name}.png")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
