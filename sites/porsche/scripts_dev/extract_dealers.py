#!/usr/bin/env python3
"""Extract dealers.json offline from cached dealersearch.html (Astro island props)."""
from __future__ import annotations

import html as H
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRAPE = BASE / "scraped_data"


def deqwik(node):
    if isinstance(node, dict):
        return {k: deqwik(v) for k, v in node.items()}
    if isinstance(node, list):
        if len(node) == 2 and isinstance(node[0], int):
            return deqwik(node[1])
        return [deqwik(x) for x in node]
    return node


def main():
    raw = (SCRAPE / "dealersearch.html").read_text()
    props = None
    for m in re.finditer(r"<astro-island[^>]*>", raw):
        pm = re.search(r'\sprops="([^"]*)"', m.group(0))
        if pm and "initialResultsGroupedByState" in pm.group(1):
            props = pm.group(1)
            break
    assert props, "dealersearch island not found"
    data = deqwik(json.loads(H.unescape(props)))
    grouped = data["initialResultsGroupedByState"]
    dealers = []
    for state in sorted(grouped):
        for rec in grouped[state]:
            dealers.append(rec["dealer"])
    (SCRAPE / "dealers.json").write_text(json.dumps(dealers, indent=1))
    states = sorted(grouped)
    print("dealers:", len(dealers), "across", len(states), "states")
    by_state = {}
    for d in dealers:
        by_state.setdefault(d["address"]["state"], 0)
        by_state[d["address"]["state"]] += 1
    print("sample states:", dict(list(by_state.items())[:8]))


if __name__ == "__main__":
    main()
