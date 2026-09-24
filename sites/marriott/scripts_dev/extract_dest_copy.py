"""Fold the real destination-page editorial copy into destinations.json.

The destination harvester (harvest_destinations.py) captures each live
/en-us/destinations/<region>.mi page as rendered HTML under
scraped_data/destination_pages/<slug>.json. This script extracts the
page's own editorial copy — the intro paragraph under the H1 and the
"Explore <City>" tab-container sections (Nature / Culture, per page) —
and injects it into source_data/destinations.json as `intro` and
`explore` so the mirror renders the same copy the live site publishes.

Resumable: re-running refreshes both fields from the captures; hotels
and other fields are left untouched.
"""
from __future__ import annotations

import html as htmllib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source_data" / "destinations.json"
PAGES = ROOT / "scraped_data" / "destination_pages"


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return htmllib.unescape(re.sub(r"\s+", " ", s)).strip()


def extract(doc: str) -> tuple:
    """Return (intro, explore sections) from a rendered destination page."""
    intro = None
    m = re.search(r'-DescriptionText"[^>]*>.*?<p>(.*?)</p>', doc, re.S)
    if m:
        text = strip_tags(m.group(1))
        if 80 < len(text) < 2500:
            intro = text

    explore = []
    labels = re.findall(
        r'custom_click_track_value="Tab Container\|([A-Za-z -]+?)-tab\|internal"',
        doc)
    panels, seen = [], set()
    for pm in re.finditer(r'leisuretabcontainer_/page-(\d+)/richtext', doc):
        if pm.group(1) in seen:
            continue
        seen.add(pm.group(1))
        panels.append(pm)
    panels.sort(key=lambda m: int(m.group(1)))
    for i, pm in enumerate(panels):
        start = pm.end()
        end = (panels[i + 1].start() if i + 1 < len(panels)
               else min(start + 30000, len(doc)))
        chunk = doc[start:end]
        paras = [strip_tags(p)
                 for p in re.findall(r"<p>(.*?)</p>", chunk, re.S)]
        paras = [p for p in paras if len(p) > 120][:4]
        label = labels[i] if i < len(labels) else f"Section {i + 1}"
        if paras:
            explore.append({"label": label, "paragraphs": paras})
    return intro, explore


def main() -> None:
    data = json.loads(SOURCE.read_text())
    n_intro = n_explore = 0
    for dest in data:
        cap = PAGES / f"{dest['slug']}.json"
        if not cap.exists():
            continue
        doc = cap.read_text(errors="ignore")
        intro, explore = extract(doc)
        if intro:
            dest["intro"] = intro
            n_intro += 1
        if explore:
            dest["explore"] = explore
            n_explore += 1
    SOURCE.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"intros: {n_intro}/{len(data)} destinations, "
          f"explore sections: {n_explore}/{len(data)}")


if __name__ == "__main__":
    main()
