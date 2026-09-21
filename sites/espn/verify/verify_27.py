#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--27.

Search on ESPN for how many teams have 'Golden' in their name and how many of
them are in the NHL.

Ground truth (hardcoded; frozen from the served /search?q=Golden page, which
returns exactly 2 teams):
    Golden State Warriors (NBA • 46-36) and Vegas Golden Knights (NHL • 45-29)
    -> 2 teams, of which exactly 1 (the Golden Knights) is NHL.

Checks: run-package gate + answer + navigation (the Golden search / the
golden-teams article / NBA & NHL team lists) + the counts 2 total / 1 NHL
(the task asks for the counts; naming the teams is optional evidence) +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        word_num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--27', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_golden_search",
            navigated_any(t, ["/search?q=golden", "golden-teams", "/nba/teams",
                              "/nhl/teams"]),
            "must search 'Golden' or browse the NBA/NHL team lists / golden-teams article")
    named = (contains_any(fa, ["warrior", "golden state"]) and
             contains_any(fa, ["golden knights", "vegas", "knight"]))
    j.check("answer_counts",
            word_num_in(fa, 2) and word_num_in(fa, 1),
            f"2 teams carry 'Golden'; 1 of them is NHL (teams named: {named})")
    j.emit()

if __name__ == "__main__":
    main()
