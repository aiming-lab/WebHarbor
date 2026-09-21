#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--11.

How many NBA teams are there and list all the teams with 'New' in their name.

Ground truth (hardcoded; frozen from the served /nba/teams page):
    The NBA has 30 teams.  Teams with 'New' in their name: New York Knicks
    and New Orleans Pelicans.

Checks: run-package gate + answer + navigation (NBA teams page / standings /
'New' search) + the count 30 + both 'New' teams + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        word_num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--11', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nba_teams",
            navigated_any(t, ["/nba/teams", "/search?q=new", "/nba/standings"]),
            "must open the NBA teams page, the standings, or a 'New' search")
    j.check("answer_thirty_teams", word_num_in(fa, 30),
            "the NBA has 30 teams")
    j.check("answer_new_teams",
            contains_any(fa, ["knick", "new york"]) and
            contains_any(fa, ["pelican", "new orleans"]),
            "the two 'New' teams: New York Knicks and New Orleans Pelicans")
    j.emit()

if __name__ == "__main__":
    main()
