#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--6.

Find the result of the latest basketball game between the Los Angeles Lakers
and the Boston Celtics, including the final score and top scorer from the
match.

Ground truth (hardcoded; frozen from the served mirror pages — the Lakers and
Celtics met on December 25, 2023 (Lakers 120-117) and most recently on
February 1, 2024 at Crypto.com Arena):
    February 1, 2024: Los Angeles Lakers 114, Boston Celtics 105 (Final).
    Game-high scorer: LeBron James 33 points (box score; Tatum 30 for Boston).

Checks: run-package gate + answer + navigation (Lakers/Celtics team pages,
game detail, scoreboard/schedule) + final score 114-105 + both teams + top
scorer LeBron 33 + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--6', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lakers_celtics_game",
            navigated_any(t, ["/game/36", "/los-angeles-lakers", "/boston-celtics",
                              "/nba/scoreboard", "/nba/schedule"]),
            "must open the Lakers/Celtics team pages, the game page, or the scoreboard/schedule")
    j.check("answer_final_score", game_score_in(fa, 114, 105),
            "latest Lakers-Celtics final: Lakers 114, Celtics 105 (Feb 1, 2024)")
    j.check("answer_teams",
            contains_any(fa, ["laker", "los angeles"]) and contains_any(fa, ["celtic", "boston"]),
            "both teams named")
    j.check("answer_top_scorer", contains_all(fa, ["lebron"]) and num_in(fa, 33),
            "game-high scorer: LeBron James 33 points")
    j.emit()

if __name__ == "__main__":
    main()
