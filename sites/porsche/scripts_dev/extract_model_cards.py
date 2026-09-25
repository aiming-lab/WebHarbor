#!/usr/bin/env python3
"""Regenerate model_cards.json offline from the cached models_overview.html.

Run from anywhere:  python3.11 scripts_dev/extract_model_cards.py

The live /usa/models/ page embeds the full ModelOverview Astro island
(76 model cards, real prices / hp / tech highlights) as an escaped-JSON
props attribute. No network needed.
"""
from __future__ import annotations

import html as H
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRAPE = BASE / "scraped_data"


def deqwik(node):
    """Astro/Qwik pair format: [int, value] tuples carry the value."""
    if isinstance(node, dict):
        return {k: deqwik(v) for k, v in node.items()}
    if isinstance(node, list):
        if len(node) == 2 and isinstance(node[0], int):
            return deqwik(node[1])
        return [deqwik(x) for x in node]
    return node


def main():
    raw = (SCRAPE / "models_overview.html").read_text()
    props = None
    for m in re.finditer(r'<astro-island[^>]*component-url="[^"]*ModelOverview[^"]*"[^>]*>', raw):
        pm = re.search(r'\sprops="([^"]*)"', m.group(0))
        if pm and "changeModel" in pm.group(1):
            props = pm.group(1)
            break
    assert props, "ModelOverview island props not found in cache"
    data = deqwik(json.loads(H.unescape(props)))
    cards = data["modelCards"]
    out = []
    for c in cards:
        out.append({"id": c.get("id", ""), "model": c["model"], "props": c["props"]})
    (SCRAPE / "model_cards.json").write_text(json.dumps(out, indent=1))
    n_hp = sum(1 for c in out if (c["model"].get("powerHp") or {}).get("formattedValue"))
    n_price = sum(1 for c in out if (c["model"].get("price") or {}).get("value"))
    ranges = sorted({c["model"].get("modelRange") for c in out})
    print("cards:", len(out), "with hp:", n_hp, "with price:", n_price)
    print("ranges:", ranges)


if __name__ == "__main__":
    main()
