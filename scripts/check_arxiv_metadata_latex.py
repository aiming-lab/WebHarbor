#!/usr/bin/env python3
"""Regression checks for arXiv metadata LaTeX cleanup."""

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARXIV_DIR = ROOT / "sites/arxiv"
PAPERS = ARXIV_DIR / "papers.json"


def main():
    sys.path.insert(0, str(ARXIV_DIR))
    from metadata_cleaning import clean_arxiv_metadata_text as clean
    from metadata_cleaning import format_arxiv_display_text as display
    papers = json.loads(PAPERS.read_text())
    by_id = {paper.get("arxiv_id"): paper for paper in papers}

    known_cases = {
        "2604.07983": {
            "contains": [r"$\gtrsim 100\times$", r"$z=1.37$", "SN 2025mkn"],
            "forbidden": [r"\gtrsim 100\times\gtrsim 100\times", "z=1.37z=1.37"],
        },
        "2604.04709": {
            "contains": [r"\mathbb{P}^1"],
            "forbidden": [r"\mathbb{P}^1\mathbb{P}^1"],
        },
        "2604.07446": {
            "contains": [r"\mathcal{N}=1"],
            "forbidden": [r"\mathcal{N}=1\mathcal{N}=1", "CFT_3_3"],
        },
        "2206.03566": {
            "contains": [r"\mathbb{R}^4"],
            "forbidden": [r"\mathbb{R}^4\mathbb{R}^4"],
        },
        "2511.23096": {
            "contains": [r"GL(d_1)\times GL(d_2)"],
            "forbidden": [r"GL(d_1)\times GL(d_2)GL(d_1)\times GL(d_2)"],
        },
    }

    for arxiv_id, checks in known_cases.items():
        paper = by_id.get(arxiv_id)
        if not paper:
            raise SystemExit(f"missing arXiv fixture {arxiv_id}")
        cleaned_title = clean(paper.get("title", ""))
        for text in checks["contains"]:
            if text not in cleaned_title:
                raise SystemExit(f"{arxiv_id}: expected cleaned title fragment missing: {text}")
        for text in checks["forbidden"]:
            if text in cleaned_title:
                raise SystemExit(f"{arxiv_id}: duplicated title fragment remains: {text}")

    display_cases = {
        r"A Natural $\gtrsim 100\times$ Telescope at $z=1.37$": [
            "≥ 100×",
            "z=1.37",
        ],
        r"Project page \url{this https URL}": [
            "Project page this https URL",
        ],
        r"available at \href{this https URL}{GitHub}": [
            "available at GitHub",
        ],
        r"$\mathbb{R}^4$ and $\mathcal{N}=2$": [
            "R^4",
            "N=2",
        ],
    }
    for raw, fragments in display_cases.items():
        rendered = display(raw)
        for fragment in fragments:
            if fragment not in rendered:
                raise SystemExit(f"display fragment missing: {fragment!r} from {rendered!r}")
        if "\\" in rendered or "$" in rendered:
            raise SystemExit(f"display still contains raw TeX delimiters: {rendered!r}")

    duplicate_patterns = [
        re.compile(r"(\\mathbb\{[^}]+\}\^?[^\\\s]*)\1"),
        re.compile(r"(\\mathcal\{[^}]+\}=?[0-9A-Za-z]*)\1"),
        re.compile(r"(\\mathrm\{[^}]+\}[_^]?\{?[^{}\s]*\}?)\1"),
        re.compile(r"\b(z=[0-9.]+)\1\b"),
        re.compile(r"(\$[^$]{1,120}\$)\s*\1"),
        re.compile(r"(GL\(d_1\)\\times GL\(d_2\))\1"),
    ]
    failures = []
    for paper in papers:
        cleaned_title = clean(paper.get("title", ""))
        for pattern in duplicate_patterns:
            if pattern.search(cleaned_title):
                failures.append((paper.get("arxiv_id"), cleaned_title))
                break
    if failures:
        preview = "\n".join(f"{pid}: {title}" for pid, title in failures[:20])
        raise SystemExit(f"duplicated LaTeX fragments remain in cleaned titles:\n{preview}")

    display_failures = []
    for paper in papers:
        for field in ("title", "abstract", "comments"):
            rendered = display(paper.get(field, ""))
            if r"\href{" in rendered or r"\url{" in rendered:
                display_failures.append((paper.get("arxiv_id"), field, rendered[:160]))
    if display_failures:
        preview = "\n".join(f"{pid} {field}: {text}" for pid, field, text in display_failures[:20])
        raise SystemExit(f"raw URL TeX commands remain in display text:\n{preview}")

    print("arXiv metadata LaTeX checks passed")


if __name__ == "__main__":
    main()
