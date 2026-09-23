#!/usr/bin/env python3
"""Build the definitive image manifest (mirror path <- upstream URL) and download."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "scraped_data"
DET = OUT / "detail_pages"
IMG = HERE / "static" / "images"
BASE = "https://www.instructure.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def clean_ext(url: str) -> str:
    path = url.split("?")[0]
    if path.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return path.rsplit(".", 1)[-1]
    # .png.webp style URLs keep the final extension
    return "png"


def slug_of(href: str) -> str:
    return href.strip("/").replace("/", "__")


def build_manifest() -> list[dict]:
    manifest: dict[str, dict] = {}

    def add(mirror_rel: str, url: str, note: str = "") -> None:
        url = url.split(" ")[0]
        if url.startswith("/"):
            url = BASE + url
        if mirror_rel in manifest:
            old = manifest[mirror_rel]["url"]
            if old != url:
                # prefer the higher-resolution style variant
                rank = lambda u: ({"large_hq": 3, "medium_hq": 2, "medium": 1}.get(
                    u.split("/styles/")[-1].split("/")[0], 0) if "/styles/" in u else 2.5)
                if rank(url) > rank(old):
                    manifest[mirror_rel] = {"url": url, "note": note}
            return
        manifest[mirror_rel] = {"url": url, "note": note}

    resources = json.loads((HERE / "source_data_resources.json").read_text(encoding="utf-8"))
    for r in resources:
        slug = r["slug"]
        if r.get("card_img"):
            add(f"resources/{slug}.{clean_ext(r['card_img'])}", r["card_img"], "card")
        elif r["type"] == "podcast":
            path = DET / f"{slug}.html"
            if path.exists():
                html = path.read_text(encoding="utf-8", errors="ignore")
                i = html.find("node--type-podcast")
                seg = html[i:i + 6000] if i >= 0 else ""
                m = re.search(r'(?:src|data-src)="(/sites/default/files/styles/medium_hq/[^\"]+)"', seg)
                if m:
                    add(f"resources/{slug}.{clean_ext(m.group(1))}", m.group(1), "podcast-hero")
        elif r.get("blog_image"):
            add(f"resources/{slug}.{clean_ext(r['blog_image'])}", r["blog_image"], "blog-hero")
        elif r["type"] in ("video", "ebook"):
            # pages linked from the upstream navigation but absent from listings:
            # fall back to the og:image card art
            path = DET / f"{slug}.html"
            if path.exists():
                html = path.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'property="og:image" content="(https://www\.instructure\.com/sites/[^"]+)"', html)
                if m:
                    add(f"resources/{slug}.{clean_ext(m.group(1))}", m.group(1), "card:og-image")
        if r["type"] == "case_study" and r.get("case_study", {}).get("logo"):
            add(f"logos/{slug}.{clean_ext(r['case_study']['logo'])}", r["case_study"]["logo"], "cs-logo")
        if r.get("author", {}).get("img"):
            au = r["author"]["img"]
            name = au.split("/")[-1].split("?")[0]
            add(f"authors/{name}", au, "author")

    # events
    events = json.loads((OUT / "listing_events.json").read_text(encoding="utf-8"))
    for e in events:
        if not e.get("img"):
            continue
        slug = e["about"].strip("/").replace("/", "__")
        add(f"events/{slug}.{clean_ext(e['img'])}", e["img"], "event-tile")

    # leaders
    misc = json.loads((HERE / "source_data_misc.json").read_text(encoding="utf-8"))
    for l in misc["leaders"]:
        slug = l["about"].strip("/").split("/")[-1]
        if l.get("card_img"):
            add(f"leaders/{slug}-card.{clean_ext(l['card_img'])}", l["card_img"], "leader-card")
        if l.get("modal_img"):
            add(f"leaders/{slug}-modal.{clean_ext(l['modal_img'])}", l["modal_img"], "leader-modal")

    # home + marketing images: pick targeted files from captured page HTML
    home = (OUT / "home_full.html").read_text(encoding="utf-8", errors="ignore")
    wanted_home = [
        r"/sites/default/files/image/2026-08/home-hero-noram-aug26-p1-cyberattacks-v1\.jpg",
        r"/sites/default/files/image/2026-08/home-hero-noram-aug26-p2-lstinsights-v1\.png",
        r"/sites/default/files/image/2026-08/home-hero-noram-aug26-p3-academicfraud-v1\.jpg",
        r"/sites/default/files/image/2026-07/home-carousel-aihub-v1\.png",
        r"/sites/default/files/image/2026-07/home-carousel-edtecht40-v1\.png",
        r"/sites/default/files/styles/large_hq/public/image/2025-06/home-3colcontent-p1-k12-v1\.jpg\?itok=[^\"' ]+",
        r"/sites/default/files/styles/large_hq/public/image/2025-06/home-3colcontent-p2-he-v1\.jpg\?itok=[^\"' ]+",
        r"/sites/default/files/styles/large_hq/public/image/2025-06/home-3colcontent-p3-bizgov-v1\.jpg\?itok=[^\"' ]+",
        r"/sites/default/files/styles/large_hq/public/image/2025-06/home-bannervideo-cover-dreambig-v1\.jpg\?itok=[^\"' ]+",
        r"/sites/default/files/image/2026-03/bg-image\.png",
        r"/sites/default/files/image/2025-07/banner-cta-fullwidth-background-brandblue-v1\.jpg",
    ]
    for pat in wanted_home:
        m = re.search(pat, home)
        if m:
            name = m.group(0).split("?")[0].rsplit("/", 1)[-1]
            add(f"home/{name}", m.group(0), "home")
    # home resource carousel / ebook + case study cover images (medium style)
    for m in re.finditer(r'src="(/sites/default/files/styles/medium/public/image/[^"]+)"', home):
        u = m.group(1)
        if "home" in u or "banner" in u:
            add(f"home/{u.split('?')[0].rsplit('/', 1)[-1]}", u, "home-style")
    # accolade + partner logos on home
    for m in re.finditer(r'src="(/sites/default/files/styles/large_hq/public/image/2025-0[67][^"]+)"', home):
        u = m.group(1)
        name = u.split("?")[0].rsplit("/", 1)[-1]
        if "award" in name or "logo" in name:
            add(f"misc/{name}", u, "home-accolade")
    for m in re.finditer(r'src="(/sites/default/files/styles/large_hq/public/image/2025-07/aws-logo\.png[^"]*)"', home):
        add("misc/aws-logo.png", m.group(1), "home-partner")

    # accolade + partner logos referenced by alt text on the home page
    for m in re.finditer(r'<img[^>]+(?:src|data-src)="([^"\s]+)"[^>]*alt="([^"]*)"', home):
        u, alt = m.group(1), m.group(2)
        if not u.startswith("/"):
            continue
        if any(k in alt.lower() for k in ["award", "badge", "logo"]) and "Clear.gif" not in u:
            name = u.split("?")[0].rsplit("/", 1)[-1]
            add(f"misc/{name}", u, f"home-alt:{alt[:30]}")
    # the ecosystem brand image
    for m in re.finditer(r'src="(/sites/default/files/[^"]*brand-3-brands-type[^"]*)"', home):
        add("misc/brand-3-brands-type-2025.png", m.group(1), "home-ecosystem")

    # marketing page heroes + section images from captured pages
    for page, keys in {
        "canvas": [r"canvas-overview-hero-canvasuser-v1\.jpg"],
        "mastery": [r"mastery[^\" ]*hero[^\" ]*\.(?:jpg|png)"],
        "parchment": [r"parchment[^\" ]*hero[^\" ]*\.(?:jpg|png)"],
        "k12": [r"k12[^\" ]*\.(?:jpg|png)"],
        "higher_education": [r"higher[^\" ]*\.(?:jpg|png)"],
        "business": [r"business[^\" ]*\.(?:jpg|png)"],
        "about": [r"about[^\" ]*\.(?:jpg|png)", r"leadership-header-image-2026\.jpg"],
        "community": [r"community[^\" ]*\.(?:jpg|png)"],
        "careers": [r"career[^\" ]*\.(?:jpg|png)"],
        "partners": [r"partner[^\" ]*\.(?:jpg|png)"],
    }.items():
        p = OUT / f"{page}.html"
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in keys:
            for m in re.finditer(r'/sites/default/files/(?:styles/[^/]+/public/)?image/[^" ]*'
                                 + pat, text):
                u = m.group(0)
                name = u.split("?")[0].rsplit("/", 1)[-1]
                add(f"misc/{name}", u, f"page:{page}")

    # case study stat icons (shared SVGs)
    icons = set()
    for r in resources:
        for st in (r.get("case_study") or {}).get("stats", []):
            if st.get("icon"):
                icons.add(st["icon"])
    for u in sorted(icons):
        name = u.split("?")[0].rsplit("/", 1)[-1]
        add(f"../icons/stat-{name}", u, "cs-stat-icon")

    rows = [{"path": k, **v} for k, v in sorted(manifest.items())]
    (HERE / "image_manifest.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"manifest: {len(rows)} images")
    return rows


def download(rows: list[dict]) -> None:
    ok = fail = 0

    def one(client: httpx.Client, row: dict) -> None:
        nonlocal ok, fail
        target = (IMG).parent / row["path"] if row["path"].startswith("../") \
            else IMG / row["path"]
        if row["path"].startswith("../"):
            target = (IMG / row["path"]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size > 0:
            return
        for attempt in range(4):
            try:
                r = client.get(row["url"])
                if r.status_code == 200 and len(r.content) > 100:
                    target.write_bytes(r.content)
                    ok += 1
                    return
                if r.status_code in (429, 502, 503):
                    time.sleep(2 + attempt * 2)
            except httpx.HTTPError:
                time.sleep(2)
        fail += 1
        print(f"  [FAIL] {row['path']} <- {row['url']}", flush=True)

    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=40) as client:
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(lambda r: one(client, r), rows))
    print(f"downloaded ok={ok} fail={fail}")


def main() -> None:
    rows = build_manifest()
    if "--download" in sys.argv:
        download(rows)


if __name__ == "__main__":
    main()
