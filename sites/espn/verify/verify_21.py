#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--21.

Show the scores and main highlight of the Denver Nuggets game that occurred
within the last 3 days on ESPN.

Ground truth (hardcoded; frozen from the served mirror pages — mirror "today"
is April 10, 2024, so the Nuggets game inside the window is):
    April 9, 2024: Golden State Warriors 109 @ Denver Nuggets 121 (Final, Ball
    Arena, TNT).  Box-score highlights: Nikola Jokic 29 points / 14 rebounds /
    12 assists (triple-double), Stephen Curry 24 points; page recap: 'Nikola
    Jokic posted a triple-double as the Nuggets cruised past Golden State to
    clinch home court advantage.'

Checks: run-package gate + answer + navigation (Nuggets pages / scoreboard /
game detail) + the 121-109 score + both teams + a real highlight + read-only
DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--21', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nuggets_game",
            navigated_any(t, ["/denver-nuggets", "/game/18", "/nba/scoreboard",
                              "/nba/schedule", "/scores"]),
            "must open the Nuggets team pages, the game page, or the scoreboard/schedule")
    j.check("answer_final_score", game_score_in(fa, 121, 109),
            "final score: Nuggets 121, Warriors 109 (Apr 9, 2024)")
    j.check("answer_teams",
            contains_any(fa, ["nugget", "denver"]) and
            contains_any(fa, ["warrior", "golden state"]),
            "both teams named")
    j.check("answer_highlight",
            (contains_all(fa, ["jokic"]) and (num_in(fa, 29) or
             contains_any(fa, ["triple-double", "triple double"])))
            or (contains_all(fa, ["curry"]) and num_in(fa, 24)),
            "highlight: Jokic 29 pts triple-double (or Curry 24)")
    j.emit()

if __name__ == "__main__":
    main()
