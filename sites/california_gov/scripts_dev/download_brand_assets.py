#!/usr/bin/env python3
"""Download the small brand assets committed to git (icons, fonts, css, js).

These are ca.gov's own design-system files: the CA.gov logo, the CaGov icon
webfont, the Public Sans body font faces referenced by the design-system CSS,
and the design system CSS/JS itself. The CSS is byte-real except that the
fonts.gstatic.com font URLs are rewritten to the local static/fonts copies so
the mirror renders offline.
"""
from __future__ import annotations

import pathlib
import re
import sys
import time

import httpx

BASE = "https://www.ca.gov"
SITE = pathlib.Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=60)


def fetch(url: str) -> bytes | None:
    if not url.startswith("http"):
        url = BASE + url
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
    icons = SITE / "static" / "icons"
    fonts = SITE / "static" / "fonts"
    css = SITE / "static" / "css"
    js = SITE / "static" / "js"
    for d in (icons, fonts, css, js):
        d.mkdir(parents=True, exist_ok=True)

    icon_files = {
        "cagov-logo.svg": "/images/CAgov-logo.svg",
        "cagov-logo-flag-gradient.svg": "/images/cagov-logo-flag-gradient.svg",
        "googleplay-download.svg": "/images/googleplay-download.svg",
        "app-store-download.svg": "/images/app-store-download.svg",
        "favicon.ico": "/favicon.ico",
    }
    for name, url in icon_files.items():
        data = fetch(url)
        if data is None:
            sys.exit(f"missing icon asset: {name}")
        (icons / name).write_bytes(data)
        print(f"icon {name}: {len(data)}B")

    # Body font: the design-system CSS references these Public Sans faces.
    css_url = "/css/cagov-custom.min.css?vjan26a"
    css_data = fetch(css_url)
    if css_data is None:
        sys.exit("missing design system css")
    css_text = css_data.decode("utf-8")
    font_urls = sorted(set(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css_text)))
    print(f"public sans faces referenced: {len(font_urls)}")
    for i, url in enumerate(font_urls, 1):
        data = fetch(url)
        if data is None:
            sys.exit(f"missing font: {url}")
        name = f"publicsans-{i}.woff2"
        (fonts / name).write_bytes(data)
        css_text = css_text.replace(url, f"../fonts/{name}")
        print(f"font {name}: {len(data)}B <- {url}")

    # The CaGov icon webfont referenced by the CSS itself.
    cagov_font = fetch("/fonts/CaGov.woff2")
    if cagov_font is None:
        sys.exit("missing CaGov.woff2")
    (fonts / "CaGov.woff2").write_bytes(cagov_font)
    print(f"font CaGov.woff2: {len(cagov_font)}B")

    (css / "cagov-custom.min.css").write_text(css_text, encoding="utf-8")
    print(f"css cagov-custom.min.css: {len(css_text)}B (fonts localized)")

    js_files = {
        "cagov-custom.min.js": "/js/cagov-custom.min.js?vjan26a",
        "custom.min.js": "/js/custom.min.js?vjan26a",
    }
    for name, url in js_files.items():
        data = fetch(url)
        if data is None:
            sys.exit(f"missing js: {name}")
        (js / name).write_bytes(data)
        print(f"js {name}: {len(data)}B")


if __name__ == "__main__":
    main()
