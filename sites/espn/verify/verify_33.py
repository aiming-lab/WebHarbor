#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--33.

Locate the latest ESPN articles discussing potential MVP candidates in the NFL
for 2023 season.

Ground truth (hardcoded; frozen from the served /nfl/news page — the 2023-MVP
candidate articles, latest first):
    'Lamar Jackson's MVP-caliber season' (January 10, 2024, Dan Graziano:
    Baltimore's quarterback stacks the resume); 'Patrick Mahomes' 2023 MVP
    candidacy: a closer look' (December 14, 2023, Adam Schefter); 'Josh Allen's
    MVP profile: still in the mix' (November 22, 2023); 'Jalen Hurts' MVP
    candidacy after 2022' (November 12, 2023).

Checks: run-package gate + answer + navigation (NFL news page, NFL section,
an MVP article, or an NFL MVP search) + the latest MVP article's subject
(Lamar Jackson) + a supporting MVP fact + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, step_urls, contains_all,
                        contains_any, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--33', a.no_llm)
    t, fa = grade_common(j, a)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any(("/nfl/news" in u) or ("/story/" in u) or ("mvp" in u)
                 or (u.rstrip("/").endswith("/nfl")) for u in urls)
    j.check("nav_nfl_mvp_coverage", nav_ok,
            "must open the NFL news page, the NFL section, an MVP article, "
            "or an NFL MVP search")
    j.check("answer_latest_mvp_article",
            contains_any(fa, ["lamar", "jackson"]),
            "the latest 2023-MVP article: Lamar Jackson's MVP-caliber season (Jan 10, 2024)")
    j.check("answer_mvp_context",
            contains_any(fa, ["baltimore", "raven", "mahomes", "josh allen",
                              "hurts", "quarterback", "qb"]),
            "the answer is anchored in the NFL MVP-candidate coverage")
    j.emit()

if __name__ == "__main__":
    main()
