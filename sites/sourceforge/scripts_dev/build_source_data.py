#!/usr/bin/env python3
"""Freeze the harvested upstream snapshots into source_data/sourceforge_catalog.json.

Inputs (tracked under source_data/): per-project Allura REST snapshots
(projects/*.json), the parsed directory/search card catalog
(catalog_cards.json), the mirror-neighborhood snippets (mirror_snippets.json),
and the 7-Zip deep-content captures. Output: one normalized catalog consumed
by seed_data.py at image build time. Run from sites/sourceforge/.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "source_data"


def norm_num(text):
    if not text:
        return None
    m = re.search(r"([\d,]+)", text.replace(",", ""))
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def main() -> None:
    cards = json.loads((SRC / "catalog_cards.json").read_text())
    mirrors = json.loads((SRC / "mirror_snippets.json").read_text())
    merged = json.loads((SRC / "merged_projects.json").read_text()) if (SRC / "merged_projects.json").exists() else None
    if merged is None:
        raise SystemExit("run the merge step first (see scripts_dev/README)")
    # unescape html entities accumulated from the scraped cards
    for name, p in merged.items():
        for k in ("name", "summary", "short_description"):
            if isinstance(p.get(k), str):
                p[k] = html.unescape(p[k]).strip()
        if isinstance(p.get("short_description"), str):
            p["short_description"] = re.sub(r"\s+", " ", p["short_description"])
    out = SRC / "sourceforge_catalog.json"
    out.write_text(json.dumps(merged, indent=0, sort_keys=True))
    print(f"[build] wrote {out} ({len(merged)} projects)")


if __name__ == "__main__":
    main()
