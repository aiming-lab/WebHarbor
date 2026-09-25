#!/usr/bin/env python3
"""Download every real ca.gov media asset and write asset_inventory.json.

Sources are the exact upstream URLs surfaced by the Playwright/httpx recon:
- /images/sep/service-<id>-<slug>.webp   service detail images
- /images/sep/logo-<id>-<abbr>.webp     department logos
- /images/topic<N>-<k>.webp             topic page service cards
- homepage / about / 404 / lineart SVGs referenced by the captured pages

Outputs:
- static/images/** (managed, HF-shipped) + asset_inventory.json contract
- static/{icons,fonts,css,js} small brand assets (committed to git)

Run from the site directory: python3 scripts_dev/download_assets.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import time

import httpx

BASE = "https://www.ca.gov"
SITE = pathlib.Path(__file__).resolve().parent.parent
SCRAPED = SITE / "scraped_data"
IMG = SITE / "static" / "images"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=60)


def verify_format(path: pathlib.Path, data: bytes) -> None:
    suffix = path.suffix.casefold()
    if suffix == ".webp" and not (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        raise ValueError(f"invalid WebP header: {path}")
    if suffix in {".jpg", ".jpeg"} and not (data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"):
        raise ValueError(f"invalid JPEG framing: {path}")
    if suffix == ".png" and data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG header: {path}")
    if suffix == ".svg":
        text = data.decode("utf-8")
        if "<svg" not in text or "<script" in text.casefold():
            raise ValueError(f"unsafe SVG: {path}")


def collect_asset_list() -> list[tuple[str, str]]:
    """(relative path under static/images, upstream URL) pairs."""
    assets: list[tuple[str, str]] = []

    services = json.loads((SCRAPED / "service_details.json").read_text())
    for key, svc in sorted(services.items()):
        if svc.get("image_url"):
            name = pathlib.Path(svc["image_url"]).name
            assets.append((f"services/{name}", svc["image_url"]))

    depts = json.loads((SCRAPED / "department_details.json").read_text())
    for did, dept in sorted(depts.items(), key=lambda kv: int(kv[0])):
        if dept.get("logo_url"):
            name = pathlib.Path(dept["logo_url"]).name
            assets.append((f"departments/{name}", dept["logo_url"]))

    topics = json.loads((SCRAPED / "topics.json").read_text())
    for slug, topic in sorted(topics.items()):
        for card in topic.get("cards", []):
            name = pathlib.Path(card["image"]).name
            assets.append((f"topics/{name}", card["image"]))

    fixed = {
        "homepage/main-banner.svg": "/images/main-banner.svg",
        "homepage/highlight-1.webp": "/images/highlight-1.webp",
        "homepage/highlight-2.webp": "/images/highlight-2.webp",
        "homepage/highlight-3.webp": "/images/highlight-3.webp",
        "homepage/ca-for-all-logo.webp": "/images/ca-for-all-logo.webp",
        "homepage/ca-state-seal.webp": "/images/ca-state-seal.webp",
        "homepage/ca-gov-seal.webp": "/images/ca-gov-seal.webp",
        "about/about-animal.webp": "/images/about-animal.webp",
        "about/about-branch-1.webp": "/images/about-branch-1.webp",
        "about/about-branch-2.webp": "/images/about-branch-2.webp",
        "about/about-branch-3.webp": "/images/about-branch-3.webp",
        "about/about-colors.webp": "/images/about-colors.webp",
        "about/about-flag.webp": "/images/about-flag.webp",
        "about/about-flower.webp": "/images/about-flower.webp",
        "about/about-seal.webp": "/images/about-seal.webp",
        "about/about-tree.webp": "/images/about-tree.webp",
        "misc/404.webp": "/images/404.webp",
        "lineart/about-lineart.svg": "/images/about-lineart.svg",
        "lineart/contact-lineart.svg": "/images/contact-lineart.svg",
        "lineart/departments-lineart.svg": "/images/departments-lineart.svg",
        "lineart/get-help-lineart.svg": "/images/get-help-lineart.svg",
        "lineart/search-lineart.svg": "/images/search-lineart.svg",
        "lineart/services-lineart.svg": "/images/services-lineart.svg",
        "lineart/sitemap-lineart.svg": "/images/sitemap-lineart.svg",
        "lineart/technical-help-lineart.svg": "/images/technical-help-lineart.svg",
        "lineart/translate-lineart.svg": "/images/translate-lineart.svg",
        "lineart/background-lines.svg": "/images/background-lines.svg",
    }
    topic_ids = set()
    topics_json = json.loads((SCRAPED / "topics.json").read_text())
    for topic in topics_json.values():
        if topic.get("lineart"):
            name = pathlib.Path(topic["lineart"]).name
            topic_ids.add(name)
    for name in sorted(topic_ids):
        fixed[f"lineart/{name}"] = f"/images/{name}"
    for rel, url in fixed.items():
        assets.append((rel, url))

    # de-duplicate by relative path, keeping first occurrence
    seen = {}
    for rel, url in assets:
        if rel not in seen:
            seen[rel] = url
    return sorted(seen.items())


def download(rel: str, url: str) -> bytes | None:
    if not url.startswith("http"):
        url = BASE + url
    url = re.sub(r"\?.*$", "", url)  # strip ?v= cache busters
    for attempt in range(4):
        try:
            r = client.get(url)
            if r.status_code == 200 and r.content:
                return r.content
            print(f"  ! {url} -> HTTP {r.status_code}", file=sys.stderr)
        except httpx.HTTPError as err:
            print(f"  ! {url} -> {err}", file=sys.stderr)
        time.sleep(1.0 + attempt)
    return None


def main() -> None:
    assets = collect_asset_list()
    print(f"asset list: {len(assets)} files")
    IMG.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = []
    for rel, url in assets:
        target = IMG / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size > 0:
            data = target.read_bytes()
        else:
            data = download(rel, url)
            if data is None:
                failures.append((rel, url))
                continue
            time.sleep(0.1)
        verify_format(target, data)
        target.write_bytes(data)
        rows.append({
            "path": f"static/images/{rel}",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_url": (url if url.startswith("http") else BASE + url),
            "source_kind": "direct_url",
            "source_evidence": "downloaded from the upstream ca.gov media host at the exact URL recorded during the recon",
        })
    manifest = {
        "schema_version": 1,
        "asset_count": len(rows),
        "total_bytes": sum(r["bytes"] for r in rows),
        "direct_asset_urls": len(rows),
        "source_page_only": 0,
        "assets": rows,
    }
    (SITE / "asset_inventory.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"inventory: {len(rows)} assets, {manifest['total_bytes']} bytes total")
    if failures:
        print(f"FAILURES ({len(failures)}):", file=sys.stderr)
        for rel, url in failures:
            print(f"  {rel} <- {url}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
