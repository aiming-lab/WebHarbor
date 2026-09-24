#!/usr/bin/env python3
"""Stage 9: build the managed-image manifest and download every real asset.

Reads source_data.json plus the homepage/blog captures and produces:
  - static/images/products/<handle>-NN.png — real product images served by the
    Shopify CDN at the width=800 policy
  - static/images/bottles/<slug>.png — real case-content bottle thumbnails
    (the same files upstream serves at width=300 in the case selectors)
  - static/images/home/... — real homepage imagery (hero slides, category
    tiles, wine-club box, premium tiles, Martha Stewart banner)
  - static/images/blog/<slug>.png|jpg — real article hero images
  - static/icons/... — small committed icon files (favicon, benefit icons,
    award medal)

Writes scraped_data/image_manifest.json (path -> upstream source URL) and
downloads each file with retries. Resumable: existing files are kept.
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

import httpx

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
IMG = BASE / "static" / "images"
ICONS = BASE / "static" / "icons"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def ext_for(url: str, default: str = ".png") -> str:
    low = url.lower().split("?")[0]
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"):
        if low.endswith(ext):
            return ext
    return default


def normalize(url: str) -> str:
    url = (url or "").strip().replace("&amp;", "&")
    if url.startswith("//"):
        url = "https:" + url
    return url


def build_manifest() -> dict:
    source = json.loads((BASE / "source_data.json").read_text())
    home = source.get("home") or {}
    manifest: dict[str, str] = {}

    # product images + case bottles
    for p in source["products"]:
        for img in p.get("images") or []:
            manifest["products/" + Path(img["path"]).name] = normalize(img["source_url"])
        for case in (p.get("case_contents") or {}).values():
            for b in case.get("bottles") or []:
                if b.get("image_path") and b.get("image_source_url"):
                    manifest["bottles/" + Path(b["image_path"]).name] = normalize(b["image_source_url"])

    # hero slides (first two, upstream serves width=2000 desktop variants)
    for i, slide in enumerate((home.get("hero") or [])[:2], start=1):
        images = slide.get("images") or []
        if images:
            manifest[f"home/hero-{i}{ext_for(images[0], '.jpg')}"] = normalize(images[0])

    # benefit icons
    for i, b in enumerate(home.get("benefits") or [], start=1):
        icon = normalize(b.get("icon") or "")
        if icon:
            manifest[f"../icons/benefit-{i}{ext_for(icon, '.svg')}"] = icon

    # category tiles
    for i, t in enumerate(home.get("category_tiles") or [], start=1):
        image = normalize(t.get("image") or "")
        if image:
            manifest[f"home/tile-{i}{ext_for(image)}"] = image

    # wine club banner image
    club_images = [normalize(u) for u in ((home.get("wine_club_banner") or {}).get("images") or [])]
    if club_images:
        manifest["home/wine-club-box" + ext_for(club_images[0], ".webp")] = club_images[0]

    # premium tiles
    premium_images = [normalize(u) for u in ((home.get("premium_tiles") or {}).get("images") or [])]
    for i, url in enumerate(premium_images[:3], start=1):
        manifest[f"home/premium-{i}{ext_for(url, '.webp')}"] = url

    # martha banner (last image of the free-shipping/martha section)
    martha_images = [normalize(u) for u in ((home.get("martha_banner") or {}).get("images") or [])]
    if martha_images:
        url = martha_images[-1]
        manifest["home/martha-stewart" + ext_for(url, ".jpg")] = url

    # blog article hero images
    for a in source.get("blog_articles") or []:
        url = normalize(a.get("image_source_url") or "")
        if url:
            manifest[f"blog/{a['handle']}{ext_for(url)}"] = url

    # committed icons
    manifest["../icons/favicon.png"] = (
        "https://macyswineshop.com/cdn/shop/files/macys-favicon.png?crop=center&height=32&width=32")
    manifest["../icons/award-medal.png"] = (
        "https://macyswineshop.com/cdn/shop/t/72/assets/award-medal.png")

    return manifest


def sniff_ext(data: bytes, current: str) -> str | None:
    """Return the format implied by the bytes when it contradicts the name."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png" if current != ".png" else None
    if data[:2] == b"\xff\xd8":
        return ".jpg" if current not in (".jpg", ".jpeg") else None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp" if current != ".webp" else None
    return None


def download(manifest: dict) -> None:
    todo = []
    renames = []
    for rel, url in sorted(manifest.items()):
        dest = (IMG / rel) if not rel.startswith("../") else (ICONS / rel.removeprefix("../icons/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            todo.append((rel, url, dest))
    print(f"[images] {len(manifest)} assets, {len(todo)} to download")

    client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=90)

    def fetch(item):
        rel, url, dest = item
        for attempt in range(5):
            try:
                r = client.get(url)
                if r.status_code == 200 and len(r.content) > 100:
                    actual = sniff_ext(r.content, dest.suffix)
                    if actual:
                        # Shopify content-negotiates some .webp-named files as
                        # JPEG; store under the extension matching the bytes and
                        # remember the corrected manifest key.
                        fixed = dest.with_suffix(actual)
                        fixed.write_bytes(r.content)
                        renames.append((rel, str(dest), str(fixed)))
                        return True
                    dest.write_bytes(r.content)
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(1.2 * (attempt + 1))
        print(f"[images] FAILED {rel} <- {url}", file=sys.stderr)
        return False

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(fetch, todo))
    ok = sum(1 for r in results if r)
    for rel, old, new in renames:
        old_key = rel if not old.endswith("_icon") else rel
        stem = pathlib.Path(old)
        fixed_rel = str(pathlib.Path(rel).with_suffix(pathlib.Path(new).suffix))
        if fixed_rel != rel:
            manifest[fixed_rel] = manifest.pop(rel)
    print(f"[images] downloaded {ok}/{len(todo)}; format fixes: {len(renames)}")


def main() -> None:
    manifest = build_manifest()
    (OUT / "image_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    download(manifest)
    total = 0
    count = 0
    for path in list(IMG.rglob("*")) + list(ICONS.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            total += path.stat().st_size
            count += 1
    print(f"[images] on disk: {count} files, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
