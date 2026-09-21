#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--18.

How many sports leagues can you choose from on the ESPN home page?

Ground truth (hardcoded; frozen from the served home page — the global
navigation bar lists exactly 12 sport/league sections):
    NFL, NBA, MLB, NHL, Soccer, NCAAF (College Football), NCAAM (Men's College
    Basketball), NCAAW (Women's College Basketball), Tennis, Golf, MMA,
    Fantasy  -> 12.

Checks: run-package gate + answer + navigation to the home page + the count
12 (digit or word) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, visited_mirror_root, contains_all, word_num_in,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--18', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_homepage", visited_mirror_root(t),
            "the task is about the ESPN home page's sport choices")
    j.check("answer_twelve_sports", word_num_in(fa, 12),
            "the home-page nav offers 12 sports/league sections")
    j.emit()

if __name__ == "__main__":
    main()
