"""Harvest project microsite pages into source_data/projects.json.

Each /project/<slug> page on the live site is a standalone microsite
template (own CSS, dark hero, fact grid). We capture the full text flow
(headings, paragraphs, list items, links) plus every image with its
resolved absolute URL.
"""
from __future__ import annotations

import html as html_mod
import json
import pathlib
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mfetch import fetch

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
BASE = "https://new.mta.info"

PROJECTS = [
    ("rockaway-line-resiliency-and-rehabilitation", "Rockaway Line Resiliency and Rehabilitation"),
    ("flushing-line", "Flushing Line"),
    ("modern-fare-gates", "Modern fare gates"),
    ("staten-island-north-shore-bus-rapid-transit", "Staten Island North Shore Bus Rapid Transit"),
    ("interborough-express", "The Interborough Express"),
    ("station-accessibility-upgrades", "Station accessibility projects"),
    ("penn-station-access", "Penn Station Access"),
    ("queens-bus-network-redesign", "Queens Bus Network Redesign"),
    ("CBDTP", "Central Business District Tolling Program"),
    ("168-st-interim-bus-terminal", "168 St Interim Bus Terminal"),
    ("42-st-connection", "42 St Connection"),
    ("renewed-astoria-line", "A renewed Astoria Line"),
    ("bronx-local-bus-network-redesign", "Bronx Local Bus Network Redesign"),
    ("brooklyn-bus-network-redesign", "Brooklyn Bus Network Redesign"),
    ("cbtc-signal-upgrades", "CBTC: Upgrading signal technology"),
    ("east-side-access", "East Side Access"),
    ("fixing-rutgers-tunnel", "Fixing the Rutgers Tunnel"),
    ("fulton-transit-center", "Fulton Transit Center"),
    ("improving-accessibility-68-st-hunter-college-station", "Improving accessibility at 68 St-Hunter College"),
]


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return html_mod.unescape(text).strip()


def extract_project(doc: str, page_url: str) -> dict:
    body = re.sub(r"<script.*?</script>", " ", doc, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)

    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = _clean(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""

    blocks: list[dict] = []
    pattern = re.compile(
        r"(<h2[^>]*>.*?</h2>|<h3[^>]*>.*?</h3>|<h4[^>]*>.*?</h4>|"
        r"<ul[^>]*>.*?</ul>|<table[^>]*>.*?</table>|<img[^>]+>)",
        re.S,
    )
    pos = 0
    for mm in pattern.finditer(body):
        between = body[pos : mm.start()]
        prose = _clean(re.sub(r"<[^>]+>", " ", between))
        if len(prose) > 2:
            blocks.append({"type": "prose", "text": prose})
        chunk = mm.group(0)
        if chunk.startswith("<img"):
            src = re.search(r'src="([^"]+)"', chunk)
            alt = re.search(r'alt="([^"]*)"', chunk)
            if src:
                url = urljoin(page_url + "/", src.group(1))
                if "link-arrow" in url or "sm-" in url or "translate" in url or "Logos/" in url:
                    pos = mm.end()
                    continue
                blocks.append({
                    "type": "image",
                    "src": url,
                    "alt": _clean(re.sub(r"<[^>]+>", " ", alt.group(1))) if alt else "",
                })
        elif chunk.startswith("<ul"):
            items = [_clean(re.sub(r"<[^>]+>", " ", li)) for li in re.findall(r"<li[^>]*>(.*?)</li>", chunk, re.S)]
            items = [i for i in items if i]
            if items:
                blocks.append({"type": "list", "items": items})
        elif chunk.startswith("<table"):
            rows = []
            for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
                cells = [_clean(re.sub(r"<[^>]+>", " ", c)) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rm.group(1), re.S)]
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append({"type": "table", "rows": rows})
        else:
            level = "h2" if chunk.startswith("<h2") else ("h3" if chunk.startswith("<h3") else "h4")
            blocks.append({"type": level, "text": _clean(re.sub(r"<[^>]+>", " ", chunk))})
        pos = mm.end()
    tail = _clean(re.sub(r"<[^>]+>", " ", body[pos:]))
    if len(tail) > 2:
        blocks.append({"type": "prose", "text": tail})

    # trim footer boilerplate
    while blocks and blocks[-1]["type"] == "prose" and (
        "Skip to" in blocks[-1]["text"] or "Privacy" in blocks[-1]["text"] or len(blocks[-1]["text"]) < 3
    ):
        blocks.pop()
    return {"title": title, "blocks": blocks}


def harvest():
    out = {}
    for slug, label in PROJECTS:
        url = f"{BASE}/project/{slug}"
        doc = fetch(url)
        if not doc:
            print(f"FAIL {slug}", flush=True)
            continue
        data = extract_project(doc, url)
        data["slug"] = slug
        data["label"] = label
        out[slug] = data
        print(f"OK {slug} ({len(data['blocks'])} blocks)", flush=True)
    (OUT / "projects.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {OUT/'projects.json'} with {len(out)} projects")


if __name__ == "__main__":
    harvest()
