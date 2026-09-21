#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--42.

Check out NCAAM standings on ESPN, what are the teams with equal wins and
losses in the America East Conference currently?

Ground truth (hardcoded; frozen from the served
/mens-college-basketball/standings page — America East table):
    Vermont 14-4; UMBC 11-7; Albany 11-7; UMass Lowell 10-10; Maine 10-10;
    Binghamton 9-9; New Hampshire 8-10; Hartford 7-11; NJIT 7-11.
    Teams whose wins equal their losses: Binghamton (9-9), UMass Lowell
    (10-10), Maine (10-10).  (Teams tied on identical records: UMBC & Albany
    at 11-7, Lowell & Maine at 10-10, Hartford & NJIT at 7-11.)

Checks: run-package gate + answer + navigation to the NCAAM standings + >=2
of the W==L teams with their 9-9 / 10-10 records, OR the full tied-records
reading (UMBC & Albany 11-7) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--42', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_ncaam_standings",
            navigated_any(t, ["/mens-college-basketball/standings", "/ncaam/standings",
                              "/mens-college-basketball", "/ncaam"]),
            "must open the NCAAM (Men's College Basketball) standings")
    wl = []
    if contains_any(fa, ["binghamton"]) and game_score_in(fa, 9, 9):
        wl.append("binghamton 9-9")
    if contains_any(fa, ["lowell", "riverhawk"]) and game_score_in(fa, 10, 10):
        wl.append("umass lowell 10-10")
    if contains_any(fa, ["maine", "black bear"]) and game_score_in(fa, 10, 10):
        wl.append("maine 10-10")
    tied = (contains_any(fa, ["umbc", "retriever"]) and contains_any(fa, ["albany", "great dane"])
            and game_score_in(fa, 11, 7))
    j.check("answer_equal_wl_teams", len(wl) >= 2 or tied,
            f"W==L teams={wl}; tied-records reading={tied}")
    j.emit()

if __name__ == "__main__":
    main()
