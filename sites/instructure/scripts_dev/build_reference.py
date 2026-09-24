#!/usr/bin/env python3
"""Build source_reference.json: every structured content block needed for the mirror."""
from __future__ import annotations

import json
import pathlib
import re

from bs4 import BeautifulSoup

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def load(name: str) -> BeautifulSoup:
    return BeautifulSoup((OUT / f"{name}.html").read_text(encoding="utf-8"), "lxml")


def faq() -> list[dict]:
    html = (OUT / "support_faq.html").read_text(encoding="utf-8")
    rows: list[dict] = []
    # blocks: micro-heading category, h2 question (with <p> inside), description answer
    # Track the most recent micro-heading category, then pair each question h2
    # with the description that immediately follows it.
    cat = ""
    pos = 0
    pattern_cat = re.compile(
        r'<div class="[^"]*field--name-field-micro-heading[^"]*"[^>]*>\s*<p>(.*?)</p>', re.S)
    pattern_q = re.compile(
        r'<h2 class="field heading field--name-field-heading[^>]*>\s*<p>(.*?)</p>\s*</h2>\s*'
        r'<div class="[^"]*field--name-field-description[^"]*"[^>]*>(.*?)</div>', re.S)
    events = []
    for m in pattern_cat.finditer(html):
        events.append((m.start(), "cat", m.group(1)))
    for m in pattern_q.finditer(html):
        events.append((m.start(), "q", m.group(1), m.group(2)))
    events.sort(key=lambda e: e[0])
    for ev in events:
        if ev[1] == "cat":
            cat = clean(re.sub(r"<[^>]+>", " ", ev[2]))
        else:
            rows.append({
                "category": cat,
                "question": clean(re.sub(r"<[^>]+>", " ", ev[2])),
                "answer": clean(re.sub(r"<[^>]+>", " ", ev[3])),
            })
    return rows


def leaders() -> list[dict]:
    html = (OUT / "leadership.html").read_text(encoding="utf-8")
    people: dict[str, dict] = {}
    order: list[str] = []
    for m in re.finditer(
            r'<article about="(/about/[^"]+)"[^>]*class="node node--type-person node--view-mode-teaser"(.*?)</article>',
            html, re.S):
        about, seg = m.group(1), m.group(2)
        if about in people:
            continue
        src = re.search(r'srcset="(/sites/[^" ]+)', seg)
        h = re.search(r'field--name-title[^>]*>([^<]+)', seg)
        title = re.search(r'field--name-field-job-title[^>]*>([^<]+)', seg)
        people[about] = {
            "about": about,
            "name": clean(h.group(1) if h else ""),
            "title": clean(title.group(1) if title else ""),
            "card_img": src.group(1) if src else None,
        }
        order.append(about)
    for m in re.finditer(r'id="person-modal-\d+"[^>]*>(.*?)(?=id="person-modal-\d+"|<div class="views-row">|\Z)', html, re.S):
        seg = m.group(1)
        about = re.search(r'about="(/about/[^"]+)"', seg)
        if not about or about.group(1) not in people:
            continue
        bio = re.search(r'field--name-field-bio.*?</div>', seg, re.S)
        linked = re.search(r'field--name-field-linkedin.*?href="([^"]+)"', seg, re.S)
        img = re.search(r'data-src="(/sites/[^"]+)"', seg)
        p = people[about.group(1)]
        p["bio"] = clean(re.sub(r"<[^>]+>", " ", bio.group(0))) if bio else ""
        p["linkedin"] = linked.group(1) if linked else None
        p["modal_img"] = img.group(1) if img else None
    return [people[a] for a in order]


def home_data() -> dict:
    soup = load("home_full")
    data: dict = {"hero_slides": [], "nav_cards": [], "stats": [], "testimonials": [],
                  "solutions_cols": [], "resources_carousel": []}
    for slide in soup.select(".hs-slide"):
        micro = slide.select_one(".hs-nav-card__micro-heading")
        title = slide.select_one(".hs-title")
        body = slide.select_one(".hs-body p")
        img = slide.select_one(".hs-col-image img")
        href = slide.select_one(".hs-btn--primary a")
        data["hero_slides"].append({
            "micro": clean(micro.get_text()) if micro else "",
            "title": clean(title.get_text()) if title else "",
            "body": clean(body.get_text()) if body else "",
            "img": (img.get("src") if img else None),
            "href": (href.get("href") if href else None),
        })
    for card in soup.select(".paragraph--type--stat-card-v2"):
        num = card.select_one(".countup-number")
        pre = card.select_one(".countup-prefix")
        suf = card.select_one(".countup-suffix")
        label = card.select_one(".field--name-field-micro-heading")
        desc = card.select_one(".field--name-field-text-long")
        data["stats"].append({
            "value": ((pre.get_text(strip=True) if pre else "") + (num.get_text(strip=True) if num else "")
                     + (suf.get_text(strip=True) if suf else "")),
            "label": clean(label.get_text()) if label else "",
            "text": clean(desc.get_text(" ")) if desc else "",
        })
    seen: set[str] = set()
    for item in soup.select(".cq__item"):
        quote = item.select_one("blockquote")
        author = item.select_one(".field--name-text-plain")
        role = item.select_one(".field--name-field-job-title")
        if not quote:
            continue
        key = clean(quote.get_text())[:80]
        if key in seen:
            continue
        seen.add(key)
        data["testimonials"].append({
            "quote": clean(quote.get_text()),
            "author": clean(author.get_text()) if author else "",
            "role": clean(role.get_text()) if role else "",
        })
    # hero nav cards under slider
    for card in soup.select(".hs-nav-card"):
        micro = card.select_one(".hs-nav-card__micro-heading")
        title = card.select_one("h3, .hs-nav-card__title")
        if title is None:
            continue
        href = card.select_one("a[href]")
        key = clean(title.get_text())[:60]
        if key and key not in seen:
            seen.add(key)
            data["nav_cards"].append({
                "micro": clean(micro.get_text()) if micro else "",
                "title": key,
                "href": href.get("href") if href else None,
            })
    return data


def community_stats() -> dict:
    soup = load("community")
    out: dict = {"stats": []}
    main = soup.select_one("main")
    for st in main.select(".field--name-field-stat-text-plain, .stat-card-v2, .paragraph--type--stat-card-v2"):
        out["stats"].append(clean(st.get_text(" ")))
    text = main.get_text(" ", strip=True)
    out["text"] = text[:1800]
    return out


def hub_hero(name: str) -> dict:
    soup = load(name)
    h1 = soup.select_one("main h1")
    desc = soup.select_one("main .field--name-field-description")
    opts = {}
    for fs in soup.select("fieldset"):
        legend = fs.select_one(".fieldset-legend")
        labels = [clean(l.get_text()) for l in fs.select("label.option")]
        if legend and labels:
            opts[clean(legend.get_text())] = labels
    return {
        "h1": clean(h1.get_text()) if h1 else "",
        "desc": clean(desc.get_text(" ")) if desc else "",
        "filters": opts,
    }


def main() -> None:
    ref = json.loads((OUT / "source_reference.json").read_text(encoding="utf-8")) \
        if (OUT / "source_reference.json").exists() else {}
    ref["faq"] = faq()
    print("faq:", len(ref["faq"]))
    ref["leaders"] = leaders()
    print("leaders:", len(ref["leaders"]))
    ref["home"] = home_data()
    print("hero:", len(ref["home"]["hero_slides"]), "stats:", len(ref["home"]["stats"]),
          "testimonials:", len(ref["home"]["testimonials"]), "nav_cards:", len(ref["home"]["nav_cards"]))
    ref["community"] = community_stats()
    for hub in ["case_studies", "ebooks", "videos", "blog", "webinars", "research", "news", "events"]:
        ref[f"hub_{hub}"] = hub_hero(hub)
    (OUT / "source_reference.json").write_text(
        json.dumps(ref, indent=1, ensure_ascii=False), encoding="utf-8")
    print("written")


if __name__ == "__main__":
    main()
