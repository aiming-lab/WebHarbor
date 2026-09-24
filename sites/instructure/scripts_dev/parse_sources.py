#!/usr/bin/env python3
"""Parse harvested detail pages + listings into the tracked source_data.json."""
from __future__ import annotations

import html as html_mod
import json
import pathlib
import re

from bs4 import BeautifulSoup

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "scraped_data"
DET = OUT / "detail_pages"
BASE = "https://www.instructure.com"

LISTINGS = {
    "case_studies": ("case_study", "Case Studies"),
    "ebooks": ("ebook", "Ebooks & Buyer's Guides"),
    "videos": ("video", "Product Demos & Videos"),
    "blog": ("blog", "Blogs"),
    "webinars": ("webinar", "On-Demand Webinars"),
    "research": ("research_report", "Research Reports"),
    "podcast": ("podcast", "Podcasts"),
    "infographic": ("infographic", "Infographics"),
    "product_overviews": ("product_overview", "Product Overviews"),
    "press": ("press_release", "Press Releases"),
}


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def parse_tags(html: str) -> dict:
    m = re.search(r"id=[\"']asset[\"']\s+data-tags=[\"']([^\"']*)[\"']", html)
    if not m:
        m = re.search(r"data-tags=[\"\']([^\"\']*)[\"\']", html)
    if not m:
        return {}
    raw = html_mod.unescape(m.group(1))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def listing_rows() -> dict:
    out = {}
    for name in LISTINGS:
        out[name] = json.loads((OUT / f"listing_{name}.json").read_text(encoding="utf-8"))
    return out


def author_from(soup: BeautifulSoup) -> dict:
    block = soup.select_one(".author-info")
    if not block:
        return {}
    a = block.select_one("a.author-link")
    img = block.select_one("img")
    name = block.select_one(".name-title")
    return {
        "href": (a.get("href") if a else None),
        "img": (img.get("src") if img else None),
        "name": clean(name.get_text()) if name else "",
    }


def case_study_extras(soup: BeautifulSoup) -> dict:
    extras: dict = {"stats": [], "logo": None, "pdf": None, "micro": None, "intro": None}
    logo = soup.select_one(".resource-container img")
    if logo:
        extras["logo"] = logo.get("src") or logo.get("data-src")
    for stat in soup.select(".paragraph--type--icon-stat"):
        icon = stat.select_one("img")
        desc = stat.select_one(".field--name-field-description")
        extras["stats"].append({
            "icon": (icon.get("src") if icon else None),
            "text": clean(desc.get_text()) if desc else "",
        })
    for a in soup.select(".stats-cta a[href], .download a[href]"):
        href = a.get("href") or ""
        if href.endswith(".pdf"):
            extras["pdf"] = href
            break
    micro = soup.select_one(".paragraph--type--header-banner-case-study .field--name-field-micro-heading")
    if micro:
        extras["micro"] = clean(micro.get_text())
    return extras


def media_extras(soup: BeautifulSoup) -> dict:
    extras: dict = {"media_id": None, "transcript": None, "pdf": None}
    m = re.search(r'wistia-player media-id="([^"]+)"', str(soup))
    if m:
        extras["media_id"] = m.group(1)
    tr = soup.select_one(".field--name-field-transcript")
    if tr:
        extras["transcript"] = clean(tr.get_text(" "))[:8000]
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        if href.endswith(".pdf"):
            extras["pdf"] = href
            break
    return extras


def body_sections(soup: BeautifulSoup) -> list[dict]:
    """Ordered body blocks: {'heading': str, 'text': str, 'html': str}."""
    root = soup.select_one("#node__content") or soup.select_one("article")
    if not root:
        return []
    blocks = []
    # blog-style: single .body-container with .field--name-body blob
    blob = root.select_one(".body-container .field--name-body")
    if not blob:
        # press / podcast / other types: body directly under node__content
        for cand in root.find_all("div", class_="field--name-body", recursive=False):
            blob = cand
            break
    if blob:
        inner = str(blob.decode_contents())[:60000]
        text = clean(blob.get_text(" "))
        blocks.append({"heading": "", "text": text, "html": inner})
        return blocks
    # case-study style: .paragraph--type--text blocks
    for para in root.select(".paragraph--type--text"):
        h = para.select_one("h2, .field--name-field-heading")
        d = para.select_one(".field--name-field-description")
        if h or d:
            blocks.append({
                "heading": clean(h.get_text()) if h else "",
                "text": clean(d.get_text(" ")) if d else "",
                "html": (str(d.decode_contents()) if d else "")[:12000],
            })
    return blocks


def parse_detail(slug: str) -> dict | None:
    path = DET / f"{slug}.html"
    if not path.exists():
        return None
    html = path.read_text(encoding="utf-8", errors="ignore")
    if len(html) < 40000:
        return None
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("main h1") or soup.select_one("h1.field--name-field-heading")
    title = clean(h1.get_text()) if h1 else ""
    og_desc = re.search(r'property="og:description" content="([^"]*)"', html)
    if og_desc:
        intro_text = clean(html_mod.unescape(og_desc.group(1)))
    else:
        desc_el = (soup.select_one("main .field--name-field-description")
                   or soup.select_one("#node__content .field--name-field-description"))
        intro_text = clean(desc_el.get_text(" ")) if desc_el else ""
    date_el = soup.select_one(".field--name-field-publication-date time, .field--name-field-publication-date")
    read_el = soup.select_one(".read-time, .field--name-field-read-time")
    row = {
        "slug": slug,
        "title": title,
        "intro": intro_text,
        "tags": parse_tags(html),
        "date": clean(date_el.get_text()) if date_el else "",
        "read_time": clean(read_el.get_text()) if read_el else "",
        "author": author_from(soup),
        "case_study": case_study_extras(soup),
        "media": media_extras(soup),
        "body": body_sections(soup),
    }
    # blog header image
    bimg = soup.select_one(".field--name-field-blog-image img, .tags img")
    if bimg:
        row["blog_image"] = bimg.get("src") or bimg.get("data-src")
    # listed topic tags
    topics = [clean(a.get_text()) for a in soup.select(".tag-list a")]
    if topics:
        row["topic_tags"] = topics
    return row


# pages linked from the live site's navigation but not present in any listing
EXTRA_RESOURCES = [
    ("video", "/resources/videos/exploring-canvas"),
    ("ebook", "/resources/ebooks/external-education-playbook"),
]


def main() -> None:
    listings = listing_rows()
    resources = []
    hrefs = set()
    for name, (rtype, label) in LISTINGS.items():
        for i, lrow in enumerate(listings[name]):
            href = lrow["href"].replace(BASE, "")
            if not href.startswith("/"):
                continue
            hrefs.add(href)
            slug = href.strip("/").replace("/", "__")
            detail = parse_detail(slug)
            row = {
                "type": rtype,
                "type_label": label,
                "href": href,
                "title": lrow.get("title") or (detail or {}).get("title") or "",
                "card_img": lrow.get("img"),
                "snippet": lrow.get("snippet") or "",
                "listing_type": lrow.get("type") or "",
            }
            if detail:
                row.update({k: detail[k] for k in
                            ("slug", "intro", "tags", "date", "read_time", "author",
                             "case_study", "media", "body", "blog_image", "topic_tags")
                            if k in detail})
            resources.append(row)
        print(f"[{name}] {len(listings[name])} rows")
    # extras: linked from upstream nav but absent from listings
    for rtype, href in EXTRA_RESOURCES:
        if href in hrefs:
            continue
        if not (DET / (href.strip("/").replace("/", "__") + ".html")).exists():
            continue
        detail = parse_detail(href.strip("/").replace("/", "__"))
        row = {
            "type": rtype,
            "type_label": {v[0]: v[1] for v in LISTINGS.values()}.get(rtype, rtype),
            "href": href,
            "title": (detail or {}).get("title", ""),
            "card_img": None,
            "snippet": (detail or {}).get("intro", "")[:180],
            "listing_type": "",
        }
        if detail:
            row.update({k: detail[k] for k in
                        ("slug", "intro", "tags", "date", "read_time", "author",
                         "case_study", "media", "body", "blog_image", "topic_tags")
                        if k in detail})
        resources.append(row)
        print(f"[extra] {rtype}: {href}")

    (HERE / "source_data_resources.json").write_text(
        json.dumps(resources, indent=1, ensure_ascii=False), encoding="utf-8")
    print("resources:", len(resources))

    # events, news, jobs, leaders, faq, home
    ref = json.loads((OUT / "source_reference.json").read_text(encoding="utf-8"))
    misc = {
        "events": json.loads((OUT / "listing_events.json").read_text(encoding="utf-8")),
        "news": json.loads((OUT / "listing_news.json").read_text(encoding="utf-8")),
        "jobs": json.loads((OUT / "listing_jobs.json").read_text(encoding="utf-8")),
        "leaders": ref["leaders"],
        "faq": ref["faq"],
        "home": ref["home"],
        "hubs": {k: v for k, v in ref.items() if k.startswith("hub_")},
    }
    (HERE / "source_data_misc.json").write_text(
        json.dumps(misc, indent=1, ensure_ascii=False), encoding="utf-8")
    print("misc written")


if __name__ == "__main__":
    main()
