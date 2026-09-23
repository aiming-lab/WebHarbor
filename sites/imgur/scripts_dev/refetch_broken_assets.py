#!/usr/bin/env python3
"""Re-fetch harvest assets that were saved as imgur HTML fallback pages.

The first harvest pass hit i.imgur.com rate limits: ~180 poster/detail
downloads stored the HTML error page instead of image bytes. This script
re-downloads every non-image file under static/images from its upstream
source URL, validates magic bytes, retries with backoff, and paces
requests. Files whose upstream content is a different format than the
local extension are renamed and their manifests updated.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.request

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "scraped_data"
IMAGES = SITE / "static" / "images"

JPEG = b"\xff\xd8"
PNG = b"\x89PNG\r\n\x1a\n"
WEBP = b"RIFF"
MP4_FTYP = b"ftyp"


def sniff(data: bytes) -> str:
    if data[:2] == JPEG:
        return ".jpg"
    if data[:8] == PNG:
        return ".png"
    if data[:4] == WEBP and data[8:12] == b"WEBP":
        return ".webp"
    if MP4_FTYP in data[:32]:
        return ".mp4"
    if data[:3] == b"GIF":
        return ".gif"
    return ""


def is_broken(path: pathlib.Path) -> bool:
    data = path.read_bytes()
    kind = sniff(data)
    if not kind:
        return True
    return kind != path.suffix.casefold().replace(".jpeg", ".jpg")


def fetch(url: str, referer: str = "https://imgur.com/") -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Referer": referer,
        "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def retry_fetch(url: str) -> bytes:
    delays = (2, 6, 15)
    last_error = None
    for attempt in range(4):
        try:
            data, ctype = fetch(url)
            if sniff(data):
                return data
            last_error = f"non-image bytes ({ctype}, {len(data)}B)"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < 3:
            time.sleep(delays[attempt])
    raise RuntimeError(f"{url}: {last_error}")


def source_urls() -> dict[str, list[str]]:
    """file path (relative to static/images) -> ordered candidate source URLs."""
    candidates: dict[str, list[str]] = {}
    selection = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    for row in selection["selected"]:
        payload = json.loads((OUT / "details" / f"{row['id']}.json").read_text(encoding="utf-8"))
        for media in payload["post"].get("media") or []:
            mid = media["id"]
            mime = media.get("mime_type")
            if mime == "video/mp4":
                candidates.setdefault(f"posts/{mid}_poster.jpg", [f"https://i.imgur.com/{mid}h.jpg"])
            else:
                urls = []
                if media.get("url"):
                    urls.append(media["url"])
                urls.append(f"https://i.imgur.com/{mid}.jpeg")
                candidates.setdefault(f"posts/{mid}_detail.jpg", urls)
    for rec in json.loads((OUT / "benchmark_posts.json").read_text(encoding="utf-8")):
        mid = rec["media_id"]
        candidates.setdefault(f"posts/{mid}_detail.jpg", [rec["detail_source"]])
    return candidates


def main() -> int:
    sources = source_urls()
    broken = []
    for path in sorted(IMAGES.rglob("*")):
        if path.is_file() and path.name != ".gitkeep" and is_broken(path):
            rel = str(path.relative_to(IMAGES))
            broken.append((path, rel))
    print(f"broken files: {len(broken)}", flush=True)

    fixed = renamed = failed = 0
    for path, rel in broken:
        urls = sources.get(rel)
        if not urls:
            # tag background removed upstream: drop the file + clear its meta
            if rel == "tags/m0iKfvv.jpg":
                meta = json.loads((OUT / "tag_meta.json").read_text(encoding="utf-8"))
                meta["wallpaper"]["background_id"] = ""
                (OUT / "tag_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
                path.unlink()
                renamed += 1
                print("dropped removed-upstream tag background: wallpaper", flush=True)
                continue
            print(f"NO SOURCE for {rel}", flush=True)
            failed += 1
            continue
        last_error = None
        for url in urls:
            try:
                data = retry_fetch(url)
                break
            except RuntimeError as exc:
                last_error = exc
        else:
            print(f"FAILED {rel}: {last_error}", flush=True)
            failed += 1
            continue
        kind = sniff(data)
        want = path.suffix.casefold().replace(".jpeg", ".jpg")
        if kind == want:
            path.write_bytes(data)
            fixed += 1
        else:
            new_path = path.with_suffix(kind)
            path.write_bytes(data)
            new_path.write_bytes(data)
            path.unlink()
            fixed += 1
            renamed += 1
            print(f"renamed {rel} -> {new_path.name} (content {kind})", flush=True)
        time.sleep(0.7)
    print(f"done: fixed={fixed} renamed={renamed} failed={failed}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
