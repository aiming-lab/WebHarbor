#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--12.

The first three Top Headlines in the current ESPN home page correspond to
which sports leagues?

Ground truth (hardcoded; frozen from the served home page's 'Top Headlines'
section, in order):
    1. 'Champions League quarter-final preview: Real Madrid vs Manchester
       City headlines second leg' — SOCCER
    2. 'NHL playoff picture comes into focus in the East' — NHL
    3. 'NBA Top Headlines: Celtics, LeBron, Embiid dominate news' — NBA
    -> Soccer, NHL, NBA (in that order).

Checks: run-package gate + answer + navigation to the home page + all three
leagues named in the correct first-mention order + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, visited_mirror_root, contains_any, first_mention,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--12', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_homepage", visited_mirror_root(t),
            "the task is about the ESPN home page's Top Headlines")
    j.check("answer_three_leagues",
            contains_any(fa, ["soccer"]) and
            (contains_any(fa, ["nhl", "hockey"])) and
            contains_any(fa, ["nba"]),
            "the first three Top Headlines are Soccer, NHL, NBA")
    s = first_mention(fa, ["soccer"])
    h = first_mention(fa, ["nhl", "hockey"])
    n = first_mention(fa, ["nba"])
    j.check("answer_league_order", None not in (s, h, n) and s < h < n,
            f"first mentions: soccer@{s} < nhl@{h} < nba@{n}")
    j.emit()

if __name__ == "__main__":
    main()
