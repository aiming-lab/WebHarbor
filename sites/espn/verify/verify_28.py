#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--28.

How many MLB teams are there and list all the teams with 'City' in their name.

Ground truth (hardcoded; frozen from the served /mlb/teams page):
    Major League Baseball has 30 teams.  The only MLB team with 'City' in its
    name is the Kansas City Royals.

Checks: run-package gate + answer + navigation (MLB teams page / standings /
'City' search) + the count 30 + the Kansas City Royals + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        word_num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--28', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_mlb_teams",
            navigated_any(t, ["/mlb/teams", "/search?q=city", "/mlb/standings"]),
            "must open the MLB teams page, the standings, or a 'City' search")
    j.check("answer_thirty_teams", word_num_in(fa, 30),
            "MLB has 30 teams")
    j.check("answer_city_team",
            contains_all(fa, ["kansas city"]) and contains_any(fa, ["royal"]),
            "the only 'City' team: Kansas City Royals")
    j.emit()

if __name__ == "__main__":
    main()
