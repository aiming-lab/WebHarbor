#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--37.

Check out LeBron James' Stats to see how many games he has played in his
career so far.

Ground truth (hardcoded; frozen from the served /player/nba/lebron-james
page — the CAREER STATS block shows):
    GP 1492 (PTS 39800, REB 11200, AST 10900).  Note: the 'LeBron James
    surpasses all-time scoring record' article states 1,490 career games, an
    internal inconsistency; both on-mirror values are accepted, with the
    player-profile stats page (1492) being the task's named source.

Checks: run-package gate + answer + navigation (player profile or the
scoring-record article) + the career games count (1492 per the stats page;
1490 per the article) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, contains_all,
                        contains_any, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--37', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lebron_stats",
            navigated_any(t, ["/player/nba/lebron-james",
                              "/story/lebron-james-all-time-scoring-record"]),
            "must open LeBron's player profile (his stats) or the scoring-record article")
    j.check("answer_career_games",
            contains_any(fa, ["1492", "1,492", "1490", "1,490"]),
            "career games played: 1492 (player page) / 1490 (article)")
    j.emit()

if __name__ == "__main__":
    main()
