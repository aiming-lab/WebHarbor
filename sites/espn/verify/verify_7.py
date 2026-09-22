#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--7.

Retrieve the final score and a brief summary of the latest NBA game played by
the Los Angeles Lakers as reported on ESPN.

Ground truth (hardcoded; frozen from the served mirror pages — the Lakers'
most recent game before the pinned date of April 10, 2024):
    April 8, 2024: Los Angeles Lakers 106 @ LA Clippers 111 (Final, Crypto.com
    Arena; Clippers won).  Box-score highlights: James Harden 30 points
    (Clippers; the page recap text says 'James Harden scored 24 points to lead
    the Clippers over the Lakers'), LeBron James 29 points (Lakers).

Checks: run-package gate + answer + navigation (Lakers pages / game detail /
scoreboard) + final score 111-106 + Clippers + a summary anchored on the
page's own recap/box facts + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--7', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lakers_game",
            navigated_any(t, ["/los-angeles-lakers", "/game/19", "/nba/scoreboard",
                              "/nba/schedule", "/scores"]),
            "must open the Lakers team pages, the game page, or the scoreboard/schedule")
    j.check("answer_final_score", game_score_in(fa, 111, 106),
            "latest Lakers game: Lakers 106, Clippers 111 (Apr 8, 2024)")
    j.check("answer_clippers_named", contains_any(fa, ["clipper"]),
            "the opponent (LA Clippers) must be named")
    j.check("answer_summary",
            (contains_all(fa, ["harden"]) and (num_in(fa, 30) or num_in(fa, 24)))
            or (contains_all(fa, ["lebron"]) and num_in(fa, 29))
            or contains_any(fa, ["lead the clippers over the lakers",
                                 "led the clippers over the lakers"]),
            "summary anchored on the page recap/box score (Harden 30/24 pts, LeBron 29)")
    j.emit()

if __name__ == "__main__":
    main()
