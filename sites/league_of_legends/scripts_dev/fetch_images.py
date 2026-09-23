#!/usr/bin/env python3
"""Download every real upstream image used by the mirror.

Reads the harvested JSON snapshots under scraped_data/ and downloads the
exact upstream URLs the live site renders (with the same CDN size params),
writing bytes under static/images/ and a manifest that records the mapping
(local path -> upstream source URL).

The manifest is consumed by build_inventory.py to produce the committed
asset_inventory.json (per-file sha256 + size + source URL).
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "scraped_data"
IMG = SITE / "static" / "images"
MANIFEST = OUT / "image_manifest.json"

SPLASH_RE = re.compile(r"/splash/([A-Za-z0-9]+)_(\d+)\.jpg")


def slugify_label(value) -> str:
    cleaned: list[str] = []
    for char in (value or "").lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "_":
            cleaned.append("_")
    return "".join(cleaned).strip("_")[:60]


def slug_from_url(url: str) -> str:
    path = urlsplit(url).path
    return path.rstrip("/").split("/")[-1].split(".")[0]


def jobs_from_champions() -> list[dict]:
    jobs: list[dict] = []
    roster = {c["slug"]: c for c in json.loads((OUT / "roster.json").read_text())}
    for path in sorted(OUT.glob("champion_*.json")):
        data = json.loads(path.read_text())
        slug = data["slug"]
        portrait = roster[slug]["portrait_url"]
        if portrait:
            jobs.append({"path": f"champions/{slug}_portrait.jpg", "url": portrait})
        for i, skin in enumerate(data.get("skins", [])):
            url = skin.get("splash_url") or ""
            match = SPLASH_RE.search(url)
            num = int(match.group(2)) if match else i
            jobs.append({"path": f"champions/{slug}_{num}_splash.jpg", "url": url})
        for ability in data.get("abilities", []):
            slot = (ability.get("slot") or "").strip().upper()
            key = {"PASSIVE": "P"}.get(slot, slot)
            if ability.get("icon_url"):
                icon_url = ability["icon_url"]
                ext = ".png" if ".png" in icon_url.lower() else Path(urlsplit(icon_url).path).suffix or ".png"
                jobs.append({"path": f"abilities/{slug}_{key}_icon{ext}", "url": icon_url})
            if ability.get("poster_url"):
                jobs.append({"path": f"abilities/{slug}_{key}_poster.jpg", "url": ability["poster_url"]})
    return jobs


def inline_image_ext(url: str) -> str:
    """Extension matching the bytes the upstream URL actually serves.

    Inline bodies reference the am-a.akamaihd.net resizer proxy whose outer
    path is extensionless (``/image?f=<ddragon url>``); the proxy answers with
    the bytes of the inner URL, so the inner path decides the extension.
    """
    parsed = urlsplit(url)
    ext = Path(parsed.path).suffix
    if not ext or ext.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        if "f=" in (parsed.query or ""):
            inner = parse_qs(parsed.query).get("f", [""])[0]
            ext = Path(urlsplit(inner).path).suffix or ".jpg"
        else:
            ext = ".jpg"
    if ext.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        ext = ".jpg"
    return ext


def inline_local_path(url: str) -> str:
    """Shared local path for an inline body image (dedupes repeated URLs)."""
    import hashlib
    ext = inline_image_ext(url)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"news/inline/{digest}{ext}"


def jobs_from_articles() -> list[dict]:
    jobs: list[dict] = []
    listing = {}
    merged = OUT / "news_items_merged.json"
    if merged.exists():
        for item in json.loads(merged.read_text()):
            listing[item["path"].rstrip("/").split("/")[-1]] = item
    for path in sorted(OUT.glob("article_*.json")):
        data = json.loads(path.read_text())
        slug = data["slug"]
        masthead = data.get("masthead") or {}
        banner = masthead.get("banner_url") or (listing.get(slug) or {}).get("banner_url") or ""
        if banner:
            if "accountingTag" not in banner:
                banner = banner.split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=1440"
            jobs.append({"path": f"news/{slug}_banner.jpg", "url": banner})
            card = banner.split("?")[0] + "?accountingTag=LoL&auto=format&fit=crop&q=80&h=240&w=427&crop=center"
            jobs.append({"path": f"news/{slug}_card.jpg", "url": card})
        for url in data.get("inline_imgs") or []:
            jobs.append({"path": inline_local_path(url), "url": url})
    return jobs


def jobs_from_homepage() -> list[dict]:
    jobs: list[dict] = []
    page = json.loads((OUT / "home_page.json").read_text())
    blades = page.get("blades", [])
    # hero backdrop fallback image (the video's poster frame)
    masthead = blades[1] if len(blades) > 1 else {}
    logo = ((masthead.get("logo") or {}).get("image") or {})
    if logo.get("url"):
        jobs.append({"path": "site/home_logo.png",
                     "url": logo["url"].split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=656"})
    # hero backdrop fallback image (the video's Rift-scene fallback frame)
    for blade in blades:
        if blade.get("type") == "iconTab" and (blade.get("header") or {}).get("title") == "PLAY":
            for i, group in enumerate(blade.get("groups", [])):
                bg = (((group.get("content") or {}).get("backdrop") or {}).get("background") or {})
                if bg.get("url"):
                    tag = slugify_label(group.get("label") or f"mode{i}")
                    jobs.append({"path": f"site/home_play_{tag}.jpg",
                                 "url": bg["url"].split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=1440"})
    # featured news cards render from the article card images (news/<slug>_card.jpg),
    # so no separate homepage copies are downloaded here.
    # champion role tabs + skins promo + play tabs
    for blade in blades:
        if blade.get("type") == "iconTab":
            label = (blade.get("header") or {}).get("title") or "tab"
            for group in blade.get("groups", []):
                media = ((group.get("content") or {}).get("media") or {})
                url = media.get("url") or ""
                if media.get("type") == "video" or not url:
                    url = (media.get("thumbnail") or {}).get("url") or url
                if not url:
                    continue
                tag = label.lower() + "_" + slug_from_url(group.get("label") or "x").lower()
                variant = "?accountingTag=LoL&auto=format&fit=fill&q=80&w=656"
                jobs.append({"path": f"site/home_{tag}.png", "url": url.split("?")[0] + variant})
        if blade.get("type") == "mediaPromo":
            bg = ((blade.get("backdrop") or {}).get("background") or {})
            if bg.get("url"):
                jobs.append({"path": "site/home_promo_backdrop.jpg",
                             "url": bg["url"].split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=1440"})
            item_media = ((blade.get("item") or {}).get("media") or {})
            if item_media.get("url"):
                jobs.append({"path": "site/home_promo_item.png",
                             "url": item_media["url"].split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=640"})
    return jobs


def jobs_from_how_to_play() -> list[dict]:
    jobs: list[dict] = []
    page_path = OUT / "how_to_play.json"
    if not page_path.exists():
        return jobs
    page = json.loads(page_path.read_text())
    for i, blade in enumerate(page.get("blades", [])):
        kind = blade.get("type")
        if kind == "centeredPromotion":
            bg = ((blade.get("backdrop") or {}).get("background") or {})
            if bg.get("type") == "image" and bg.get("url"):
                jobs.append({"path": f"site/howtoplay_cp{i}.jpg",
                             "url": bg["url"].split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=1440"})
            item_media = ((blade.get("item") or {}).get("media") or {})
            if item_media.get("url"):
                jobs.append({"path": f"site/howtoplay_cp{i}_item.png",
                             "url": item_media["url"].split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=640"})
        elif kind == "iconTab":
            head = ((blade.get("header") or {}).get("title") or f"tab{i}")
            for group in blade.get("groups", []):
                media = ((group.get("content") or {}).get("media") or {})
                url = media.get("url") or (media.get("thumbnail") or {}).get("url") or ""
                if not url:
                    continue
                tag = slugify_label(head) + "_" + slugify_label(group.get("label") or "x")
                jobs.append({"path": f"site/howtoplay_{tag}.png",
                             "url": url.split("?")[0] + "?accountingTag=LoL&auto=format&fit=fill&q=80&w=656"})
    return jobs


CHROME_URLS = [
    # ESRB rating mark shown in the footer (riotbar asset served by the CMS)
    ("site/esrb.png", "https://cmsassets.rgpub.io/sanity/images/dsfx7636/riotbar/7e684cc4765a7d059f9018e16717472d7082dc37-65x97.png?&h=100&fit=max"),
    # Riot fist mark used in the riotbar (served at h=50)
    ("site/riot_fist.svg", "https://cmsassets.rgpub.io/sanity/images/dsfx7636/riotbar_live/cad193769d6a9b38ffa8b098404819b52810c94c-128x128.svg?&h=50&fit=max"),
]


def jobs_from_classic() -> list[dict]:
    """Images for the League of Legends Classic surface (/classic/ and
    /classic/champions/), captured from the upstream classic pages."""
    classic_path = OUT / "classic_page.json"
    if not classic_path.exists():
        return []
    data = json.loads(classic_path.read_text())
    # The upstream classic page addresses Wukong by its page slug (wukong),
    # but the mirror's champion route uses the ddragon key (monkeyking);
    # tile art is stored under the mirror slug so templates can derive the
    # path from the champion link target.
    tile_slug_map = {"wukong": "monkeyking"}
    jobs: list[dict] = []
    for path, url in data.get("landing_images", {}).items():
        jobs.append({"path": path, "url": url})
    for champ in data.get("champions", []):
        slug = tile_slug_map.get(champ["slug"], champ["slug"])
        jobs.append({
            "path": f"classic/champ_tiles/{slug}.jpg",
            "url": champ["tile_url"],
        })
    return jobs


def jobs_from_external_cards() -> list[dict]:
    """Card images for the external weblink cards shown on news pages."""
    import hashlib
    jobs: list[dict] = []
    hub = json.loads((OUT / "news_list.json").read_text())
    for item in hub:
        url = item.get("path") or ""
        if url.startswith("/en-us/news/"):
            continue
        banner = item.get("banner_url") or ""
        if not banner:
            continue
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        slug = f"link-{digest}"
        card = banner.split("?")[0] + "?accountingTag=LoL&auto=format&fit=crop&q=80&h=240&w=427&crop=center"
        jobs.append({"path": f"news/{slug}_card.jpg", "url": card})
    return jobs


def _format_ok(path: str, data: bytes) -> bool:
    suffix = Path(path).suffix.casefold()
    if suffix == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if suffix in {".jpg", ".jpeg"}:
        return data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
    if suffix == ".png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if suffix == ".gif":
        return data[:3] == b"GIF"
    if suffix == ".svg":
        return b"<svg" in data[:2000].casefold()
    if suffix == ".mp4":
        return b"ftyp" in data[:32]
    return True


def download(client: httpx.Client, job: dict) -> dict:
    dest = IMG / job["path"]
    if dest.exists() and dest.stat().st_size > 0:
        return {"path": job["path"], "url": job["url"], "status": "exists"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""
    # URLs harvested from rendered DOM carry HTML-escaped ampersands; the
    # upstream CDN needs the real query string to serve the intended format.
    url = html.unescape(job["url"])
    # cmsassets answers auto=format with WebP bytes for non-browser clients
    # (and some assets are stored upstream as WebP behind .jpg paths); pin the
    # rendition format so .jpg/.png targets receive bytes matching the name.
    target_ext = Path(job["path"]).suffix.casefold().lstrip(".")
    if "cmsassets.rgpub.io" in url and target_ext in {"jpg", "jpeg", "png"} and "fm=" not in url:
        fm = "jpg" if target_ext in {"jpg", "jpeg"} else "png"
        url = url + ("&" if "?" in url else "?") + f"fm={fm}"
    for attempt in range(4):
        try:
            resp = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
                "Referer": "https://www.leagueoflegends.com/",
            })
            resp.raise_for_status()
            data = resp.content
            if not data:
                raise ValueError("empty body")
            if not _format_ok(job["path"], data):
                raise ValueError(
                    f"format mismatch for {job['path']}: {data[:4]!r}")
            dest.write_bytes(data)
            return {"path": job["path"], "url": url, "status": "ok", "bytes": len(data)}
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.5 * (attempt + 1))
    return {"path": job["path"], "url": url, "status": "failed", "error": last_error[:200]}


def main() -> int:
    jobs: list[dict] = []
    jobs += jobs_from_champions()
    try:
        jobs += jobs_from_articles()
    except FileNotFoundError:
        print("[images] no article snapshots yet; skipping article images")
    try:
        jobs += jobs_from_external_cards()
    except FileNotFoundError:
        pass
    jobs += jobs_from_homepage()
    jobs += jobs_from_how_to_play()
    jobs += jobs_from_classic()
    jobs += [{"path": p, "url": u} for p, u in CHROME_URLS]
    # dedupe by path
    seen: dict[str, dict] = {}
    for job in jobs:
        if not job.get("url"):
            continue
        seen.setdefault(job["path"], job)
    jobs = list(seen.values())
    print(f"[images] {len(jobs)} unique images to download")
    results = []
    with httpx.Client(follow_redirects=True, timeout=30, http2=False) as client:
        with ThreadPoolExecutor(max_workers=16) as pool:
            for i, result in enumerate(pool.map(lambda j: download(client, j), jobs), 1):
                results.append(result)
                if i % 200 == 0:
                    print(f"  {i}/{len(jobs)} ...", flush=True)
    manifest = {}
    failures = []
    for r in results:
        if r["status"] == "failed":
            failures.append(r)
        else:
            manifest[r["path"]] = r["url"]
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    ok = sum(1 for r in results if r["status"] in ("ok", "exists"))
    print(f"[images] downloaded/present {ok}/{len(jobs)}; manifest -> {MANIFEST.name}")
    if failures:
        for f in failures[:20]:
            print("  FAIL:", f["path"], f.get("error"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
