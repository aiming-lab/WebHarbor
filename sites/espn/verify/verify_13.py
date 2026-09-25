#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--13.

Identify today's top headline in the Basketball section of ESPN, and summarize
the main points of that article.

Ground truth (hardcoded; frozen from the served /nba/ 'TOP STORIES' section —
the first headline is):
    'NBA Top Headlines: Celtics, LeBron, Embiid dominate news' (April 9,
    2024).  Body: 'The NBA is buzzing with news: the Boston Celtics clinch
    best record, LeBron James breaks the all-time scoring record, Joel Embiid
    ruled out with knee injury, and the playoff picture takes shape across
    both conferences.'

Checks: run-package gate + answer + navigation (NBA section / the article) +
the three main points (Celtics best record, LeBron scoring record, Embiid knee
injury) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--13', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nba_section",
            navigated_any(t, ["/nba/", "/story/nba-top-headlines"]),
            "must open the NBA section or the top-headlines article")
    j.check("answer_three_subjects",
            contains_any(fa, ["celtic"]) and contains_any(fa, ["lebron"])
            and contains_any(fa, ["embiid"]),
            "top headline covers Celtics, LeBron, Embiid")
    points = [
        contains_any(fa, ["best record", "64-18", "best regular season"]),
        contains_any(fa, ["all-time scoring", "39,000", "39000", "scoring record",
                          "39,800", "39800"]),
        contains_any(fa, ["knee", "indefinitely", "injur", "ruled out"]),
    ]
    j.check("answer_main_points", sum(1 for p in points if p) >= 2,
            f"summary points matched={sum(1 for p in points if p)}/3 "
            "(Celtics best record / LeBron scoring record / Embiid knee injury)")
    j.emit()

if __name__ == "__main__":
    main()
