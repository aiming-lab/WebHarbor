#!/usr/bin/env python3
"""Stage 4: capture the Wine 101 blog and the key storefront pages.

- /blogs/wine-101 index (all pages) + every article page (from the blog
  sitemap), saved as HTML for later parsing.
- The main content pages linked from the header/nav/footer: wine-club,
  contact, faq, shipping-policy, gift-guide, wedding-wine-shop,
  wine-101-lp, subscription-lp, the award spotlight page, and the
  gift-card product page.

Saves HTML under scraped_data/blog_html/ and scraped_data/page_html/.
Resumable.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import httpx

SITE = "https://macyswineshop.com"
BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

PAGES = [
    "pages/wine-club",
    "pages/contact",
    "pages/faq",
    "pages/shipping-policy",
    "pages/gift-guide",
    "pages/wedding-wine-shop",
    "pages/wine-101-lp",
    "pages/subscription-lp",
    "pages/other_im_2025_award_sd_0",
    "products/giftcard",
    "pages/terms",
    "pages/privacy",
]


def fetch(cx: httpx.Client, url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    for attempt in range(4):
        try:
            r = cx.get(url, headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200:
                dest.write_text(r.text)
                return True
            if r.status_code == 404:
                print(f"  [404] {url}")
                return False
            print(f"  [warn] {url} -> {r.status_code}")
        except httpx.HTTPError as exc:
            print(f"  [retry] {url}: {exc}")
            time.sleep(2 * (attempt + 1))
    return False


def main() -> None:
    blog_dir = OUT / "blog_html"
    page_dir = OUT / "page_html"
    blog_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True, timeout=60) as cx:
        # blog article URLs from the sitemap
        r = cx.get(f"{SITE}/sitemap_blogs_1.xml", headers={"User-Agent": UA})
        urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
        articles = [u for u in urls if "/blogs/wine-101/" in u]
        print(f"[blog] {len(articles)} article urls")
        for i, url in enumerate(articles):
            slug = url.rstrip("/").split("/")[-1]
            fetch(cx, url, blog_dir / f"{slug}.html")
            if (i + 1) % 20 == 0:
                print(f"[blog] {i + 1}/{len(articles)}")
            time.sleep(0.2)

        # blog index pages (pagination)
        page = 1
        while True:
            dest = blog_dir / f"__index_p{page}.html"
            url = f"{SITE}/blogs/wine-101?page={page}"
            if not dest.exists():
                r = cx.get(url, headers={"User-Agent": UA}, timeout=60)
                if r.status_code != 200:
                    break
                dest.write_text(r.text)
            html = dest.read_text()
            if f"page={page + 1}" not in html:
                break
            page += 1
            time.sleep(0.2)
        print(f"[blog] index pages: {page}")

        for path in PAGES:
            slug = path.replace("/", "_")
            ok = fetch(cx, f"{SITE}/{path}", page_dir / f"{slug}.html")
            print(f"[page] {path}: {'ok' if ok else 'MISSING'}")
            time.sleep(0.2)
    print("[blog/pages] done")


if __name__ == "__main__":
    main()
