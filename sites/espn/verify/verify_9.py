#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--9.

Search on ESPN for how many teams have Los Angeles in their name and how many
of them are NBA.

Ground truth (hardcoded; frozen from the served /search?q=Los%20Angeles page,
which returns exactly 8 teams):
    Los Angeles Lakers (NBA 47-35), Los Angeles Chargers (NFL), Los Angeles
    Rams (NFL), Los Angeles Kings (NHL), Los Angeles Angels (MLB), Los Angeles
    Dodgers (MLB), Los Angeles LA Galaxy (SOCCER), Los Angeles LAFC (SOCCER)
    -> 8 teams, of which exactly 1 (the Lakers) is NBA.  (The site's
    'Los Angeles sports scene' article additionally counts the LA Clippers,
    giving 9/2; either source is accepted, matching its own numbers.)

Checks: run-package gate + answer + navigation (the Los Angeles search or the
LA article) + counts consistent with one of the two sources (naming the teams
is optional evidence) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        word_num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--9', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_la_search_or_article",
            navigated_any(t, ["/search?q=los", "/story/los-angeles-sports-teams"]),
            "must search 'Los Angeles' or open the LA sports-teams article")
    search_reading = (word_num_in(fa, 8) and word_num_in(fa, 1))
    article_reading = (word_num_in(fa, 9) and word_num_in(fa, 2)
                       and contains_any(fa, ["clipper"]))
    j.check("answer_counts", search_reading or article_reading,
            "8 teams / 1 NBA (search page) or 9 teams / 2 NBA (article incl. LA Clippers)")
    j.emit()

if __name__ == "__main__":
    main()
