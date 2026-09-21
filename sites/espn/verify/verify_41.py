#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--41.

Find out which four teams the NFC North contains in the NFL on ESPN.

Ground truth (hardcoded; frozen from the served /nfl/teams page):
    NFC North: Chicago Bears (7-10), Detroit Lions (12-5), Green Bay Packers
    (9-8), Minnesota Vikings (7-10).

Checks: run-package gate + answer + navigation (NFL teams page / standings) +
all four teams named + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--41', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nfl_teams",
            navigated_any(t, ["/nfl/teams", "/nfl/standings"]),
            "must open the NFL teams page or standings")
    j.check("answer_four_teams",
            contains_any(fa, ["bear", "chicago"]) and
            contains_any(fa, ["lion", "detroit"]) and
            contains_any(fa, ["packer", "green bay"]) and
            contains_any(fa, ["viking", "minnesota"]),
            "NFC North: Bears, Lions, Packers, Vikings")
    j.emit()

if __name__ == "__main__":
    main()
