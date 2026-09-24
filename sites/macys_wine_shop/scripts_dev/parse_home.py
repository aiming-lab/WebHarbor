#!/usr/bin/env python3
"""Stage 6: parse the captured homepage DOM into a structured section map.

Reads scraped_data/design/home_after_gate.html (post-hydration capture of the
live homepage) and writes scraped_data/home_parsed.json with every section in
upstream order: announcement slides, hero slides, benefit strip, category
tiles, the "What we're loving right now" tabbed carousels (with product
handles), the wine-club banner, the premium tiles, the free-shipping band,
the Martha Stewart banner, the blog cards, the Shop-by-Price tiles, and the
footer columns.
"""
from __future__ import annotations

import html as html_mod
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
SRC = OUT / "design" / "home_after_gate.html"


def unescape(text: str) -> str:
    return html_mod.unescape(re.sub(r"\s+", " ", text)).strip()


def clean(fragment: str) -> str:
    frag = re.sub(r"<script.*?</script>", "", fragment, flags=re.S)
    frag = re.sub(r"<style.*?</style>", "", frag, flags=re.S)
    frag = re.sub(r"<svg.*?</svg>", "", frag, flags=re.S)
    return frag


def texts(fragment: str) -> list[str]:
    frag = clean(fragment)
    raw = re.sub(r"<[^>]+>", "\x00", frag)
    return [unescape(t) for t in raw.split("\x00") if unescape(t)]


def images(fragment: str) -> list[str]:
    frag = clean(fragment)
    return [html_mod.unescape(m.group(1)) for m in re.finditer(r'<img[^>]*src="([^"]+)"', frag)]


def links(fragment: str) -> list[str]:
    frag = clean(fragment)
    return [html_mod.unescape(m.group(1)) for m in re.finditer(r'<a[^>]*href="([^"]+)"', frag)]


def sections(html: str) -> dict[str, str]:
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'id="shopify-section-([a-z0-9_-]+)"', html)]
    out = {}
    for (start, name), (nxt, _) in zip(marks, marks[1:] + [(len(html), "END")]):
        out[name] = html[start:nxt]
    return out


def parse_announcement(header: str) -> list:
    slides = []
    seen = set()
    idx = header.find("announcement-bar__link")
    chunk = header[idx:idx + 20000] if idx > 0 else header
    for m in re.finditer(r'<p>(.*?)</p>', chunk, re.S):
        t = texts(m.group(1))
        joined = " ".join(t)
        key = re.sub(r"\s+", "", joined)[:60]
        if t and len(joined) > 18 and key not in seen:
            seen.add(key)
            slides.append({"parts": t, "text": joined})
    return slides


def parse_hero(free_gifts: str) -> list:
    hero = []
    for m in re.finditer(r'data-slide="(\d+)">\s*(.*?)(?=data-slide="\d+">|ai-slideshow-nav)', free_gifts, re.S):
        frag = m.group(2)
        heading_m = re.search(r'<h2[^>]*>(.*?)</h2>', frag, re.S)
        sub_m = re.search(r'ai-slideshow-subheading-[^"]+">(.*?)</div>', frag, re.S)
        button_m = re.search(r'<a href="([^"]+)"[^>]*class="ai-slideshow-button', frag)
        imgs = images(frag)
        hero.append({
            "slide": int(m.group(1)),
            "heading": texts(heading_m.group(1)) if heading_m else [],
            "subheading": [unescape(t) for t in re.split(r"</p>", re.sub(r"<[^>]+>", " ", sub_m.group(1)))] if sub_m else [],
            "button_link": html_mod.unescape(button_m.group(1)) if button_m else None,
            "images": imgs,
        })
    return hero


def parse_benefits(icon_row: str) -> list:
    out = []
    for m in re.finditer(r'ai-icon-row__column-[^"\s]+">(.*?)(?=ai-icon-row__column-|</div>\s*</div>\s*</div>\s*</div>)', icon_row, re.S):
        frag = m.group(1)
        img = images(frag)
        strong_m = re.search(r"<p><strong>(.*?)</strong></p>\s*<p>(.*?)</p>", frag, re.S)
        if strong_m:
            out.append({"icon": img[0] if img else None,
                        "title": unescape(re.sub(r'<[^>]+>', '', strong_m.group(1))),
                        "sub": unescape(re.sub(r'<[^>]+>', '', strong_m.group(2)))})
    return out


def parse_category_tiles(tile_section: str) -> list:
    out = []
    for m in re.finditer(r'<a[^>]*href="(/collections/[^"]+)"[^>]*>(.*?)</a>', tile_section, re.S):
        frag = m.group(2)
        img = images(frag)
        txt = texts(frag)
        if txt:
            out.append({"link": html_mod.unescape(m.group(1)), "label": txt[0], "image": img[0] if img else None})
    return out


def parse_featured(featured: str) -> dict:
    tab_buttons = re.findall(r"x-on:click=\"activeCollection = '([a-z0-9-]+)'\"[^>]*>\s*([^<]+?)\s*</button>", featured)
    # panels keyed by the same slug: x-bind:class="activeCollection === 'slug' ..."
    panels = re.split(r"x-bind:class=\"activeCollection === '", featured)
    tabs = {}
    names = {}
    for slug, label in tab_buttons:
        names[slug] = label.strip()
    for panel in panels[1:]:
        m = re.match(r"([a-z0-9-]+)'", panel)
        if not m:
            continue
        slug = m.group(1)
        cards = []
        for cm in re.finditer(r"window\.location\.href\s*=\s*(?:&quot;|[\"'])/products/([a-z0-9-]+)", panel):
            handle = cm.group(1)
            if handle not in cards:
                cards.append(handle)
        if cards:
            tabs[slug] = cards
    tab_labels = [names.get(slug, slug) for slug in tabs]
    return {"title": "What we’re loving right now", "tabs": tab_labels, "tab_products": tabs}


def parse_banner(banner_section: str) -> dict:
    txt = texts(banner_section)
    img = images(banner_section)
    lnk = links(banner_section)
    return {"texts": txt, "images": img, "links": lnk}


def parse_blog_cards(blog_section: str) -> list:
    out = []
    for m in re.finditer(r'<a[^>]*href="(/blogs/wine-101/[^"]+)"[^>]*>(.*?)</a>', blog_section, re.S):
        frag = m.group(2)
        img = images(frag)
        txt = texts(frag)
        out.append({
            "link": html_mod.unescape(m.group(1)),
            "title": txt[0] if txt else None,
            "excerpt": " ".join(txt[1:]) or None,
            "image": img[0] if img else None,
        })
    return out


def parse_shop_by_price(section: str) -> list:
    out = []
    for m in re.finditer(r'<a[^>]*href="(/collections/[^"]+)"[^>]*>(.*?)</a>', section, re.S):
        frag = m.group(2)
        img = images(frag)
        txt = texts(frag)
        label = txt[0] if txt else None
        if label and not any(o["label"] == label for o in out):
            out.append({"label": label, "link": html_mod.unescape(m.group(1)), "image": img[0] if img else None})
    return out


def parse_footer(footer: str) -> dict:
    txt = texts(footer)
    lnk = []
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', footer, re.S):
        label = texts(m.group(2))
        lnk.append({"href": html_mod.unescape(m.group(1)), "label": label[0] if label else ""})
    return {"texts": txt, "links": lnk}


def main() -> None:
    html = SRC.read_text(encoding="utf-8", errors="replace")
    sec = sections(html)
    header = sec.get("header", "")
    free_gifts = sec.get("free-gifts", "")
    icon_row = sec.get("template--23635409961249__1770825221b604a6d7", "")
    tiles = sec.get("template--23635409961249__88c1f531-e37d-49af-8a04-8f0975db70c8", "")
    featured = sec.get("template--23635409961249__166377520474ee6f59", "")
    club = sec.get("template--23635409961249__17713548833e835964", "")
    premium = sec.get("template--23635409961249__784f2daa-4c3e-443d-a6f5-7f27b676b475", "")
    freeship_martha = sec.get("template--23635409961249__8aa424e5-27b9-4fbf-9f0c-373fd2ff22e7", "")
    blog = sec.get("template--23635409961249__04e9c99f-39a1-444b-b1b9-82e284b2c578", "")
    shop_price = sec.get("template--23635409961249__1771447215d5115f96", "")
    footer = sec.get("footer", "")

    data = {
        "announcement": parse_announcement(header),
        "hero": parse_hero(free_gifts),
        "benefits": parse_benefits(icon_row),
        "category_tiles": parse_category_tiles(tiles),
        "featured": parse_featured(featured),
        "wine_club_banner": parse_banner(club),
        "premium_tiles": parse_banner(premium),
        "free_shipping_band": parse_banner(freeship_martha),
        "martha_banner": parse_banner(freeship_martha),
        "blog_cards": parse_blog_cards(blog),
        "shop_by_price": parse_shop_by_price(shop_price),
        "footer": parse_footer(footer),
    }
    (OUT / "home_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print("[home] sections:", {k: (len(v) if isinstance(v, list) else list(v.keys()) if isinstance(v, dict) else 1)
                               for k, v in data.items()})


if __name__ == "__main__":
    main()
