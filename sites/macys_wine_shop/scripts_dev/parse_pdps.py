#!/usr/bin/env python3
"""Stage 5: parse the captured PDP HTML files into structured JSON.

Extracts, per product:
  - wine info specs (Winery / Varietal / Year / Type / ABV / Country / Region)
    from the main product tables (``<tr><td>Label</td><td>Value</td>``)
  - award entries (medal level, year, competition)
  - pack variant case contents: bottle count, red/white split and every bottle
    (number, image, title, specs, price) from the per-variant case blocks
  - pack size options (labels, prices, per-bottle prices)
  - the "You May Also Like" related product handles
  - quick-view payloads (id, title, price, compareAtPrice, percentageOff,
    subheading, specs, imageUrl) for every product referenced anywhere

Writes scraped_data/pdp_parsed.json and scraped_data/quickview_data.json.
"""
from __future__ import annotations

import html as html_mod
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "scraped_data"
PDP_DIR = OUT / "pdp_html"

SPEC_KEYS = ("Winery", "Varietal", "Year", "Type", "ABV", "Country", "Region")

MAIN_TABLE_ROW = re.compile(
    r"<tr>\s*<td[^>]*>\s*(" + "|".join(SPEC_KEYS) + r")\s*</td>\s*<td[^>]*>\s*([^<]*?)\s*</td>",
    re.S)

MOBILE_SPEC_PAIR = re.compile(
    r"<p class=['\"]font-bold['\"]>\s*(" + "|".join(SPEC_KEYS) + r")\s*</p>\s*<p>\s*([^<]*?)\s*</p>",
    re.S)

AWARD_PATTERN = re.compile(
    r"award-medal\.png[^>]*alt='Award Medal'\s*>\s*</div>\s*<div>\s*"
    r"<span[^>]*>\s*(Double Gold|Gold|Silver|Bronze|Platinum)\s*</span>\s*"
    r"<span>([^<]*)</span>\s*<span>([^<]*)</span>",
    re.S)

QV_PATTERN = re.compile(r"\$dispatch\(\s*'quick-view'\s*,\s*\{(.*?)\}\s*\)", re.S)

CASE_HEAD = re.compile(
    r"x-show=['\"](\d+)\s*===\s*variantId['\"][^>]*>\s*<p[^>]*>\s*(\d+)\s*Bottles In This Case\s*</p>\s*"
    r"<p[^>]*>\s*((?:(?!</p>).)*?)</p>", re.S)


def unescape(text: str) -> str:
    return html_mod.unescape(text).strip()


def parse_main_specs(html: str) -> dict:
    rows = {}
    for m in MAIN_TABLE_ROW.finditer(html):
        key, value = m.group(1), unescape(m.group(2))
        if key not in rows and value:
            rows[key] = value
    return rows


def parse_awards(html: str) -> list:
    awards = []
    for m in AWARD_PATTERN.finditer(html):
        entry = {
            "level": unescape(m.group(1)),
            "year": unescape(m.group(2)).rstrip("-").strip(),
            "competition": unescape(m.group(3)),
        }
        if entry not in awards:
            awards.append(entry)
    return awards


def parse_qv_body(body: str) -> dict:
    entry = {}
    for key in ("id", "firstAvailableVariantId", "percentageOff"):
        mm = re.search(rf"\b{key}:\s*`?([0-9]+)", body)
        if mm:
            entry[key] = int(mm.group(1))
    for key in ("title", "subheading", "winery", "varietal", "year", "type",
                "abv", "country", "region", "url", "imageUrl", "price",
                "compareAtPrice"):
        mm = re.search(rf"\b{key}:\s*`([^`]*)`", body)
        if mm:
            entry[key] = unescape(mm.group(1))
    for key in ("onSale", "available"):
        mm = re.search(rf"\b{key}:\s*(true|false)", body)
        if mm:
            entry[key] = mm.group(1) == "true"
    return entry


def parse_quickviews(html: str) -> list:
    out = []
    for m in QV_PATTERN.finditer(html):
        entry = parse_qv_body(m.group(1))
        if entry.get("title"):
            out.append(entry)
    return out


def parse_case_contents(html: str) -> dict:
    """Per-variant case contents for pack products."""
    heads = list(CASE_HEAD.finditer(html))
    cases = {}
    for i, head in enumerate(heads):
        variant_id = head.group(1)
        start = head.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
        block = html[start:end]
        # per-bottle: image (alt=title) -> numbered badge -> specs -> dispatch
        bottles = []
        bottle_marks = list(re.finditer(
            r"<img[^>]*src=['\"]([^'\"]+)['\"][^>]*alt=['\"]([^'\"]+)['\"][^>]*>", block))
        candidates = [bm for bm in bottle_marks if bm.group(2).strip()]
        for j, bm in enumerate(candidates):
            b_start = bm.start()
            b_end = candidates[j + 1].start() if j + 1 < len(candidates) else len(block)
            bblock = block[b_start:b_end]
            number = None
            nm = re.search(r"<span[^>]*text-white[^>]*>\s*(\d+)\s*</span>", bblock)
            if not nm:
                nm = re.search(r"<span[^>]*>\s*(\d+)\s*</span>\s*(?:</[^>]+>\s*)*<p[^>]*>\s*bottle\s*</p>", bblock)
            if nm:
                number = int(nm.group(1))
            specs = {}
            for sm in MOBILE_SPEC_PAIR.finditer(bblock):
                key, value = sm.group(1), unescape(sm.group(2))
                if key not in specs and value:
                    specs[key] = value
            dispatch = None
            dm = QV_PATTERN.search(bblock)
            if dm:
                dispatch = parse_qv_body(dm.group(1))
            image = bm.group(1)
            title = unescape(bm.group(2))
            if title and number:
                bottles.append({
                    "number": number,
                    "title": title,
                    "image": image,
                    "specs": specs,
                    "quickview": dispatch,
                })
        if bottles:
            cases[variant_id] = {
                "count": int(head.group(2)),
                "split": clean_split(head.group(3)),
                "bottles": bottles,
            }
    return cases


def clean_split(raw: str) -> str:
    text = html_mod.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(\d)\s*(Red|White|Rosé|Rose|Sparkling|Sweet)", r"\1 \2", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_pack_sizes(html: str) -> list:
    sizes = []
    for m in re.finditer(
            r"<input[^>]*type=['\"]radio['\"][^>]*value=['\"]([^'\"]+)['\"][^>]*name=['\"]size['\"][^>]*>",
            html):
        value = m.group(1)
        after = html[m.end():m.end() + 2200]
        label_m = re.search(r"<label[^>]*>\s*<span>([^<]*)</span>\s*<span[^>]*>\s*([^<]*?)\s*</span>", after, re.S)
        pp = re.search(r"(\$[0-9][0-9.,]*)\s*</span>\s*per bottle", after)
        sizes.append({
            "value": value,
            "label": unescape(label_m.group(1)).rstrip(":").strip() if label_m else value,
            "price": unescape(label_m.group(2)) if label_m else None,
            "per_bottle": unescape(pp.group(1)) if pp else None,
        })
    return sizes


def parse_related(html: str) -> list:
    idx = html.find("You May Also Like")
    if idx < 0:
        return []
    block = html[idx:idx + 80000]
    handles = []
    for m in re.finditer(r"window\.location\.href\s*=\s*[\"']/products/([a-z0-9-]+)", block):
        if m.group(1) not in handles:
            handles.append(m.group(1))
    return handles[:12]


def main() -> None:
    products = json.loads((OUT / "products_visible.json").read_text())
    parsed = {}
    quickview: dict[str, dict] = {}
    for p in products:
        handle = p["handle"]
        path = PDP_DIR / f"{handle}.html"
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        parsed[handle] = {
            "handle": handle,
            "specs": parse_main_specs(html),
            "awards": parse_awards(html),
            "case_contents": parse_case_contents(html),
            "pack_sizes": parse_pack_sizes(html),
            "related": parse_related(html),
        }
        for qv in parse_quickviews(html):
            url = qv.get("url") or ""
            h = url.rstrip("/").split("/")[-1]
            if h and h not in quickview:
                quickview[h] = qv
    (OUT / "pdp_parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=1))
    (OUT / "quickview_data.json").write_text(json.dumps(quickview, ensure_ascii=False, indent=1))
    with_specs = sum(1 for v in parsed.values() if v["specs"])
    with_cases = sum(1 for v in parsed.values() if v["case_contents"])
    with_awards = sum(1 for v in parsed.values() if v["awards"])
    with_sizes = sum(1 for v in parsed.values() if v["pack_sizes"])
    n_bottles = sum(len(c["bottles"]) for v in parsed.values() for c in v["case_contents"].values())
    print(f"[parse] {len(parsed)} pdps | specs {with_specs} | cases {with_cases} ({n_bottles} bottles) | "
          f"sizes {with_sizes} | awards {with_awards} | qv {len(quickview)}")


if __name__ == "__main__":
    main()
