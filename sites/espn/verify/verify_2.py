#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--2.

Show the scores and main highlight of the Milwaukee Bucks game that took place
within the last 2 days on ESPN.

Ground truth (hardcoded; frozen from the served mirror pages — mirror "today"
is April 10, 2024, so the Bucks game inside the window is):
    April 9, 2024, Indiana Pacers 114 @ Milwaukee Bucks 119 (Final, Fiserv
    Forum).  Box-score highlights: Giannis Antetokounmpo 35 points and 12
    rebounds (Bucks), Tyrese Haliburton 22 points / 11 assists (Pacers);
    page recap: 'Giannis Antetokounmpo dominated with 35 points and 12
    rebounds as the Bucks held off the Pacers in a tight contest.'

Checks: run-package gate + answer + navigation (Bucks pages / NBA scoreboard /
schedule / game detail) + the final score + both teams + a real highlight +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--2', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_bucks_game",
            navigated_any(t, ["/milwaukee-bucks", "/game/17", "/nba/scoreboard",
                              "/nba/schedule", "/scores"]),
            "must open the Bucks team pages, the NBA scoreboard/schedule, or the game page")
    j.check("answer_final_score", game_score_in(fa, 119, 114),
            "final score: Bucks 119, Pacers 114")
    j.check("answer_teams",
            contains_any(fa, ["buck", "milwaukee"]) and contains_any(fa, ["pacer", "indiana"]),
            "both teams named")
    j.check("answer_highlight",
            (contains_all(fa, ["giannis", "antetokounmpo"]) and (num_in(fa, 35) or num_in(fa, 12)))
            or (contains_all(fa, ["giannis"]) and num_in(fa, 35))
            or (contains_all(fa, ["haliburton"]) and num_in(fa, 22))
            or (contains_all(fa, ["lillard"]) and num_in(fa, 22)),
            "highlight: Giannis 35 pts (12 reb) / Haliburton 22 pts")
    j.emit()

if __name__ == "__main__":
    main()
