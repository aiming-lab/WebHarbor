#!/usr/bin/env python3
"""Download the imgur mirror's real upstream media assets.

Stage 3: for the selected catalog (selection.json + scraped_data/details/),
download every media variant the mirror serves — feed thumbnails, detail
images, small videos, avatars, tag backgrounds, comment images — plus the
site chrome (fonts, icons, accolades, favicons) that is committed to git
under static/icons/.

Outputs:
  sites/imgur/static/images/**   (HF-managed runtime assets)
  sites/imgur/static/icons/**    (committed chrome)
  scraped_data/asset_manifest.json (per-file source URL mapping)
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import time

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
IMAGES = SITE / "static" / "images"
ICONS = SITE / "static" / "icons"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

DETAIL_MAX_ORIGINAL = 1_500_000
GIF_WEBP_MAX = 3_000_000
VIDEO_MAX = 2_500_000

CHROME = {
    # s.imgur.com desktop-assets chrome (committed under static/icons/)
    "fonts/proxima-nova-regular.woff2": "desktop-assets/fonts/proxima-nova-regular.woff2",
    "fonts/proxima-nova-bold.woff2": "desktop-assets/fonts/proxima-nova-bold.woff2",
    "fonts/proxima-nova-extrabold.woff2": "desktop-assets/fonts/proxima-nova-extrabold.woff2",
    "fonts/imgur.woff": "desktop-assets/fonts/imgur.woff",
    "homebg.png": "desktop-assets/homebg.f51d3f34235dea1b7cdd.png",
    "icon-new-post.svg": "desktop-assets/icon-new-post.da483e9d9559c3b4e912.svg",
    "icon-new-meme.svg": "desktop-assets/icon-new-meme.2aa65f808a1476b35608.svg",
    "icon-open-arcade.svg": "desktop-assets/icon-open-arcade.e4e1016a6ef16660d0ff.svg",
    "icon-filter.svg": "desktop-assets/icon-filter.eb136cd5b8fa2cc73236.svg",
    "icon-upvote.svg": "desktop-assets/icon-upvote.1a004310dde3a4539205.svg",
    "icon-downvote.svg": "desktop-assets/icon-downvote.1a004310dde3a4539205.svg",
    "icon-heart.svg": "desktop-assets/icon-heart.ddabef7ecdb00c633b26.svg",
    "icon-share.svg": "desktop-assets/icon-share.8cb2b5d81d5b6084129c.svg",
    "icon-pause.svg": "desktop-assets/icon-pause.b2e8f67db9f540ee5f4a.svg",
    "icon-photo.svg": "desktop-assets/icon-photo.e5fd72ac37a762a402ea.svg",
    "icon-browse.svg": "desktop-assets/browse.7a7c32874c696f6255a8.svg",
    "icon-meme-block.svg": "desktop-assets/meme.1719bac60b7861cbd5e9.svg",
    "upload-close.svg": "desktop-assets/upload_dialog_close.090c128bffd440597750.svg",
    "icon-full-screen.png": "desktop-assets/icon-full-screen.406001126bdee1a788e0.png",
    "icon-volume-disabled.svg": "desktop-assets/icon-volume-disabled.d6793cf7b736c90f8d17.svg",
    "favicon-32x32.png": "../images/favicon-32x32.png",
    "favicon-96x96.png": "../images/favicon-96x96.png",
}
ACCOLADES = ["back", "best", "entertaining", "gem", "intriguing", "originality", "pizza"]


class Fetcher:
    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=60, follow_redirects=True,
            headers={"User-Agent": UA, "Referer": "https://imgur.com/",
                     "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"})
        self.manifest: dict[str, str] = {}
        self.stats = {"downloaded": 0, "skipped": 0, "bytes": 0}

    def get(self, url: str) -> bytes | None:
        for attempt in range(4):
            try:
                r = self.client.get(url)
                if r.status_code == 429:
                    wait = 20 * (attempt + 1)
                    print(f"  429 {url[:80]} waiting {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.content
            except httpx.HTTPError as error:
                print(f"  http error {error}; retry {url[:80]}", flush=True)
                time.sleep(8)
        return None

    def download(self, url: str, path: pathlib.Path) -> bool:
        if path.exists() and path.stat().st_size > 0:
            self.stats["skipped"] += 1
            self.manifest[str(path.relative_to(SITE))] = url
            return True
        data = self.get(url)
        if not data:
            print(f"  MISSING {url[:100]} -> {path.name}", flush=True)
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.stats["downloaded"] += 1
        self.stats["bytes"] += len(data)
        self.manifest[str(path.relative_to(SITE))] = url
        return True


def imgur_variant(media_id: str, suffix: str, ext: str, maxwidth: int | None = None) -> str:
    url = f"https://i.imgur.com/{media_id}{suffix}.{ext}"
    if maxwidth:
        url += f"?maxwidth={maxwidth}"
    return url


def main() -> int:
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    details_dir = OUT / "details"
    fetcher = Fetcher()

    # ------------------------------------------------------------------ media
    wanted: dict[str, dict] = {}
    for row in selection["selected"]:
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        post = payload["post"]
        for media in post.get("media") or []:
            mid = media["id"]
            if mid in wanted:
                continue
            mime = media.get("mime_type")
            entry = {"post": row["id"], "mime": mime, "ext": media.get("ext"),
                     "size": media.get("size") or 0}
            if mime in ("image/jpeg", "image/png"):
                entry["feed"] = imgur_variant(mid, "_d", "webp", 520)
                if entry["size"] <= DETAIL_MAX_ORIGINAL:
                    entry["detail"] = media["url"]
                else:
                    entry["detail"] = imgur_variant(mid, "", "h.jpg")
            elif mime == "image/gif":
                entry["feed"] = imgur_variant(mid, "_d", "webp", 520)
                entry["detail"] = entry["feed"]  # animated webp variant
            elif mime == "video/mp4":
                if entry["size"] > VIDEO_MAX:
                    continue
                entry["feed"] = media["url"]
                entry["detail"] = media["url"]
                entry["poster"] = imgur_variant(mid, "", "h.jpg")
            else:
                continue
            wanted[mid] = entry

    print(f"downloading {len(wanted)} media items", flush=True)
    for n, (mid, entry) in enumerate(sorted(wanted.items()), 1):
        ext_map = {"feed": ("posts", "feed"), "detail": ("posts", "detail"), "poster": ("posts", "poster")}
        for kind, (folder, prefix) in ext_map.items():
            if kind not in entry:
                continue
            url = entry[kind]
            if url.endswith(".mp4"):
                name = f"{mid}.mp4"
            elif url.endswith(".webp"):
                name = f"{mid}_{prefix}.webp"
            elif ".jpg?maxwidth" in url or url.endswith(".jpg"):
                name = f"{mid}_{prefix}.jpg"
            else:
                name = f"{mid}_{prefix}.{url.rsplit('.', 1)[-1].split('?')[0]}"
            fetcher.download(url, IMAGES / folder / name)
        if n % 50 == 0:
            print(f"  media {n}/{len(wanted)} (dl={fetcher.stats['downloaded']})", flush=True)

    # ------------------------------------------------------------------ avatars
    avatars: dict[str, str] = {}
    for row in selection["selected"]:
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        account = (payload["post"].get("account") or {})
        if account.get("avatar"):
            avatars[account["username"]] = account["avatar"]
        blob = payload.get("comments") or {}
        for comment in blob.get("data") or []:
            for target in [comment] + (comment.get("comments") or []):
                acc = target.get("account") or {}
                if acc.get("avatar") and acc.get("username"):
                    avatars.setdefault(acc["username"], acc["avatar"])

    print(f"downloading {len(avatars)} avatars", flush=True)
    for username, url in sorted(avatars.items()):
        if not url.startswith("https://"):
            continue
        fetcher.download(url, IMAGES / "avatars" / f"{username}.png")

    # ------------------------------------------------------------------ comment images
    comment_images = set()
    for row in selection["selected"]:
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        blob = payload.get("comments") or {}
        for comment in blob.get("data") or []:
            for target in [comment] + (comment.get("comments") or []):
                text = (target.get("comment") or "").strip()
                if re.fullmatch(r"https://i\.imgur\.com/[A-Za-z0-9]+\.(?:jpg|jpeg|png|gif|webp)", text):
                    comment_images.add(text.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    print(f"downloading {len(comment_images)} comment images", flush=True)
    for mid in sorted(comment_images):
        fetcher.download(imgur_variant(mid, "_d", "jpg", 800), IMAGES / "comments" / f"{mid}.jpg")

    # ------------------------------------------------------------------ tag backgrounds
    tags = set()
    for row in selection["selected"]:
        tags.update(row.get("feed_tags") or [])
        payload = json.loads((details_dir / f"{row['id']}.json").read_text(encoding="utf-8"))
        for t in payload["post"].get("tags") or []:
            if t.get("tag"):
                tags.add(t["tag"])
    tag_meta = json.loads((OUT / "tag_meta.json").read_text(encoding="utf-8"))
    bg_hashes = set()
    for name in tags:
        meta = tag_meta.get(name) or {}
        if meta.get("background_id"):
            bg_hashes.add(meta["background_id"])
    for name, meta in tag_meta.items():
        if meta.get("background_id"):
            bg_hashes.add(meta["background_id"])
    print(f"downloading {len(bg_hashes)} tag backgrounds", flush=True)
    for bg in sorted(bg_hashes):
        fetcher.download(imgur_variant(bg, "_d", "jpg", 800), IMAGES / "tags" / f"{bg}.jpg")

    # ------------------------------------------------------------------ trophies
    trophies = set()
    for row in selection["selected"]:
        pass  # trophies are fetched per mirrored member in harvest_members.py
    # s.imgur.com static trophy set
    for name in ["10_years", "post_of_the_day"]:
        url = f"https://s.imgur.com/images/trophies/{name}.png"
        fetcher.download(url, ICONS / "trophies" / f"{name}.png")

    # ------------------------------------------------------------------ accolades + chrome
    for name in ACCOLADES:
        fetcher.download(f"https://s.imgur.com/images/accolades/{name}.png",
                         ICONS / "accolades" / f"{name}.png")
    for local, remote in CHROME.items():
        fetcher.download(f"https://s.imgur.com/{remote}", ICONS / local)

    (OUT / "asset_manifest.json").write_text(
        json.dumps(fetcher.manifest, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")
    print(f"done: {fetcher.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
