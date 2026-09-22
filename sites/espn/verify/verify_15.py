#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--15.

Check the scores of the NBA games played on December 25, 2023.

Ground truth (hardcoded; frozen from the served /nba/scoreboard?date=20231225
page — five Christmas Day games):
    Celtics 117 @ Lakers 120; Celtics 122 @ Warriors 115; Knicks 101 @ Bucks
    108; Warriors 114 @ Nuggets 127; Heat 102 @ 76ers 110.

Checks: run-package gate + answer + navigation (the dated scoreboard, the
schedule, or all-scores) + >=4 of the 5 games with teams and correct scores +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, norm, game_score_in,
                        Judge, parse_args)

XMAS_GAMES = [
    (["celtic", "boston"], ["laker", "los angeles"], 117, 120),
    (["celtic", "boston"], ["warrior", "golden state"], 122, 115),
    (["knick", "new york"], ["buck", "milwaukee"], 101, 108),
    (["warrior", "golden state"], ["nugget", "denver"], 114, 127),
    (["heat", "miami"], ["76er", "philadelphia", "sixers"], 102, 110),
]

def main():
    a = parse_args()
    j = Judge('ESPN--15', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_dated_scores",
            navigated_any(t, ["20231225", "/nba/scoreboard", "/nba/schedule", "/scores"]),
            "must open the dated NBA scoreboard, the schedule, or all-scores")
    f = norm(fa)
    matched = []
    for away, home, asc, hsc in XMAS_GAMES:
        if (any(x in f for x in away) and any(x in f for x in home)
                and game_score_in(fa, asc, hsc)):
            matched.append((away[0], home[0], asc, hsc))
    j.check("answer_four_xmas_games", len(matched) >= 4,
            f"matched={len(matched)}/5: {matched}")
    j.emit()

if __name__ == "__main__":
    main()
