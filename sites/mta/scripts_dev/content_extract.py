"""Extract structured content blocks from captured new.mta.info Drupal pages.

Every content page on the live site follows the same Drupal layout:
`region region-content` holds an `mta-page-title` block, then a sequence of
paragraph blocks (headings, prose, lists, images, link-groups, tables).
This module converts that into a JSON-able block list.
"""
from __future__ import annotations

import html as html_mod
import re


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return html_mod.unescape(text).strip()


def _strip_tags(fragment: str) -> str:
    return _clean_text(re.sub(r"<[^>]+>", " ", fragment))


def _content_region(doc: str) -> str | None:
    i = doc.find('class="region region-content"')
    if i < 0:
        i = doc.find("region region-content")
    if i < 0:
        return None
    j = doc.find("<footer", i)
    if j < 0:
        j = len(doc)
    region = doc[i:j]
    # drop the opening container div itself so its attributes don't leak
    close = region.find(">")
    if close > 0:
        region = region[close + 1 :]
    return region


def _block_images(fragment: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<img[^>]+>", fragment):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        alt = re.search(r'alt="([^"]*)"', tag)
        if not src:
            continue
        url = src.group(1)
        if "gstatic.com" in url:
            continue
        out.append({"src": url, "alt": _clean_text(alt.group(1)) if alt else ""})
    return out


def _block_links(fragment: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', fragment, re.S):
        href, inner = m.group(1), m.group(2)
        text = _strip_tags(inner)
        if not text or href.startswith("#"):
            continue
        out.append({"href": href, "text": text})
    return out


def extract_blocks(doc: str) -> dict | None:
    """Return {'title': str, 'blocks': [...]} for a captured Drupal page."""
    region = _content_region(doc)
    if region is None:
        return None

    m = re.search(r"<h1[^>]*>(.*?)</h1>", region, re.S)
    title = _strip_tags(m.group(1)) if m else ""

    blocks: list[dict] = []
    # Split the region into paragraph-level chunks at h2/h3 boundaries and
    # paragraph--type boundaries.
    pattern = re.compile(
        r"(<h2[^>]*>.*?</h2>|<h3[^>]*>.*?</h3>|<h4[^>]*>.*?</h4>|"
        r"<div[^>]*paragraph--type--link-group.*?</div>\s*</div>|"
        r"<a[^>]*class=\"[^\"]*mta-card[^\"]*\"[^>]*>.*?</a>|"
        r"<table[^>]*>.*?</table>|"
        r"<ul[^>]*>.*?</ul>|"
        r"<img[^>]+>)",
        re.S,
    )
    pos = 0
    for m in pattern.finditer(region):
        # capture interstitial prose between structural blocks
        between = region[pos : m.start()]
        prose = _strip_tags(between)
        if len(prose) > 2:
            blocks.append({"type": "prose", "text": prose})
        chunk = m.group(0)
        if chunk.startswith("<h2"):
            blocks.append({"type": "h2", "text": _strip_tags(chunk)})
        elif chunk.startswith("<h3"):
            blocks.append({"type": "h3", "text": _strip_tags(chunk)})
        elif chunk.startswith("<h4"):
            blocks.append({"type": "h4", "text": _strip_tags(chunk)})
        elif chunk.startswith("<img"):
            blocks.append({"type": "image", "images": _block_images(chunk)})
        elif chunk.startswith("<table"):
            # parse rows
            rows = []
            for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
                cells = [
                    _strip_tags(cm)
                    for cm in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rm.group(1), re.S)
                ]
                if any(cells):
                    rows.append(cells)
            blocks.append({"type": "table", "rows": rows})
        elif "paragraph--type--link-group" in chunk:
            blocks.append({"type": "links", "links": _block_links(chunk)})
        elif 'class="mta-card' in chunk or "class='mta-card" in chunk or "mta-card " in chunk[:200]:
            # upstream card links (e.g. the airport guide's per-airport cards)
            blocks.append({"type": "links", "links": _block_links(chunk)})
        elif chunk.startswith("<ul"):
            items = [
                _strip_tags(li)
                for li in re.findall(r"<li[^>]*>(.*?)</li>", chunk, re.S)
            ]
            items = [i for i in items if i]
            if items:
                blocks.append({"type": "list", "items": items})
        pos = m.end()
    tail = _strip_tags(region[pos:])
    if len(tail) > 2:
        blocks.append({"type": "prose", "text": tail})

    # de-duplicate consecutive prose blocks
    merged: list[dict] = []
    for b in blocks:
        if (
            b["type"] == "prose"
            and merged
            and merged[-1]["type"] == "prose"
        ):
            merged[-1]["text"] = merged[-1]["text"] + " " + b["text"]
        else:
            merged.append(b)
    return {"title": title, "blocks": merged}


def extract_hero_image(doc: str) -> str | None:
    """Hero/banner image for a page (files.mta.info banner or first content img)."""
    for m in re.finditer(r'<img[^>]+src="(https://files\.mta\.info/[^"]+)"', doc):
        return m.group(1)
    return None


def extract_updated(doc: str) -> str | None:
    m = re.search(r"Updated ([A-Z][a-z]+ \d{1,2}, \d{4})", doc)
    return m.group(1) if m else None
