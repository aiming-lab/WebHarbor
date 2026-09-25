"""Harvest press releases into source_data/press_releases.json.

The /press-release listing is JS-rendered (a Drupal view behind a Vue
wrapper); drive WebKit (Akamai accepts the WebKit fingerprint) to get the
listing, then fetch each article page server-side and extract its content.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from content_extract import _content_region, _clean_text, _strip_tags
from mfetch import fetch

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
BASE = "https://new.mta.info"


def list_releases(max_pages: int = 4) -> list[dict]:
    from playwright.sync_api import sync_playwright

    results: list[dict] = []
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.webkit.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(BASE + "/press-release", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        for pageno in range(0, max_pages):
            items = page.evaluate(
                """() => {
                    const out = [];
                    document.querySelectorAll('a[href*="/press-release/"]').forEach(a => {
                        const card = a.closest('article, .views-row, .card, [class*="press"], li') || a.parentElement;
                        const date = card ? (card.querySelector('[class*="date"], time')?.innerText || '') : '';
                        out.push({href: a.getAttribute('href'), text: a.innerText.trim(), date: date.trim()});
                    });
                    return out;
                }"""
            )
            new = 0
            for it in items:
                href = it["href"] or ""
                if not href.startswith("/press-release/") or href == "/press-release":
                    continue
                if href in seen:
                    continue
                seen.add(href)
                results.append(it)
                new += 1
            print(f"page {pageno}: +{new} (total {len(results)})", flush=True)
            if new == 0:
                break
            # click the Next pager button for the following page
            try:
                next_link = page.query_selector('a[rel="next"]')
                if next_link is None:
                    break
                next_link.scroll_into_view_if_needed()
                next_link.click()
                page.wait_for_timeout(3500)
            except Exception as exc:  # noqa: BLE001
                print("pager stop:", str(exc)[:80], flush=True)
                break
        browser.close()
    return results


def extract_article(doc: str) -> dict | None:
    region = _content_region(doc)
    if region is None:
        region = doc
    m = re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S)
    title = _clean_text(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""
    blocks = []
    pattern = re.compile(
        r"(<h2[^>]*>.*?</h2>|<h3[^>]*>.*?</h3>|<ul[^>]*>.*?</ul>|<ol[^>]*>.*?</ol>|"
        r"<table[^>]*>.*?</table>|<img[^>]+>)",
        re.S,
    )
    pos = 0
    for mm in pattern.finditer(region):
        between = region[pos : mm.start()]
        prose = _strip_tags(between)
        if len(prose) > 2:
            blocks.append({"type": "prose", "text": prose})
        chunk = mm.group(0)
        if chunk.startswith("<img"):
            src = re.search(r'src="([^"]+)"', chunk)
            if src and "files.mta.info" in src.group(1):
                blocks.append({"type": "image", "src": src.group(1)})
        elif chunk.startswith(("<ul", "<ol")):
            items = [_strip_tags(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", chunk, re.S)]
            items = [i for i in items if i]
            if items:
                blocks.append({"type": "list", "items": items})
        elif chunk.startswith("<table"):
            rows = []
            for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
                cells = [_strip_tags(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rm.group(1), re.S)]
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append({"type": "table", "rows": rows})
        else:
            level = "h2" if chunk.startswith("<h2") else "h3"
            blocks.append({"type": level, "text": _strip_tags(chunk)})
        pos = mm.end()
    tail = _strip_tags(region[pos:])
    if len(tail) > 2:
        blocks.append({"type": "prose", "text": tail})
    return {"title": title, "blocks": blocks}


# Press releases linked from content pages but not on the first listing pages.
EXTRA_RELEASES = [
    "/press-release/mta-announces-first-ever-paratransit-electric-vehicles-joining-access-ride-fleet",
    "/press-release/mta-awarded-federal-grant-protect-nyc-transit-westchester-train-yard-flooding",
    "/press-release/mta-protect-metro-north-hudson-line-against-effects-of-climate-change",
    "/press-release/icymi-governor-hochul-announces-early-completion-of-major-structural-replacement-of",
]


def harvest():
    listing = list_releases()
    seen_hrefs = {it["href"] for it in listing}
    for href in EXTRA_RELEASES:
        if href not in seen_hrefs:
            listing.append({"href": href, "text": "", "date": ""})
    out = []
    for it in listing:
        url = BASE + it["href"]
        doc = fetch(url)
        if not doc:
            print(f"FAIL {it['href']}", flush=True)
            continue
        art = extract_article(doc)
        if not art or not art["title"]:
            print(f"EMPTY {it['href']}", flush=True)
            continue
        art["path"] = it["href"]
        art["date"] = it.get("date", "")
        art["listing_title"] = it.get("text", "")
        out.append(art)
        print(f"OK {it['href']} ({len(art['blocks'])} blocks)", flush=True)
    (OUT / "press_releases.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {OUT/'press_releases.json'} with {len(out)} releases")


if __name__ == "__main__":
    harvest()
