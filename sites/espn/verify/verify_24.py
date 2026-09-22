#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--24.

Find the final score from the most recent NFL game broadcast on ESPN,
including the teams' names and the date of the match (the broadcast-network reading and the most-recent-game reading are both accepted).

Ground truth (hardcoded; frozen from the served /nfl/scoreboard page — two
    defensible readings of the task wording are accepted):
    (a) broadcast-network reading — the most recent NFL games BROADCAST ON
    ESPN are both from January 21, 2024: Green Bay Packers 21 @ San
    Francisco 49ers 24 (Final, Levi's Stadium) and Houston Texans 10 @
    Baltimore Ravens 34 (Final, M&T Bank Stadium);
    (b) site reading — the most recent NFL game shown on ESPN overall is
    Super Bowl LVIII, February 11, 2024: Kansas City Chiefs 22 @ San
    Francisco 49ers 25 (Final OT, Levi's Stadium).

Checks: run-package gate + answer + navigation (NFL scoreboard/schedule/game
pages) + one accepted game with both teams, the final score, and the correct
match date (Jan 21 for the ESPN-broadcast pair, Feb 11 for the Super Bowl) +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, norm, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--24', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nfl_scores",
            navigated_any(t, ["/nfl/scoreboard", "/nfl/schedule", "/scores", "/game/"]),
            "must open the NFL scoreboard/schedule, all-scores, or a game page")
    f = norm(fa)
    packers = (contains_any(fa, ["packer", "green bay"])
               and contains_any(fa, ["49er", "san francisco"])
               and game_score_in(fa, 24, 21)
               and ("january 21" in f or "jan 21" in f or "1/21" in f or "2024-01-21" in f))
    texans = (contains_any(fa, ["texan", "houston"])
              and contains_any(fa, ["raven", "baltimore"])
              and game_score_in(fa, 34, 10)
              and ("january 21" in f or "jan 21" in f or "1/21" in f or "2024-01-21" in f))
    superbowl = (contains_any(fa, ["chief", "kansas city"])
                 and contains_any(fa, ["49er", "san francisco"])
                 and game_score_in(fa, 25, 22)
                 and ("february 11" in f or "feb 11" in f or "2/11" in f or "2024-02-11" in f))
    j.check("answer_recent_nfl_game", packers or texans or superbowl,
            "accepted: Packers 21-24 49ers / Texans 10-34 Ravens (Jan 21, ESPN) or "
            "Super Bowl LVIII Chiefs 22-25 49ers (Feb 11)")
    j.emit()

if __name__ == "__main__":
    main()
