#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--23.

Find the result of the latest basketball game between the Miami Heat and the
New York Knicks, including the final score and top rebounder from the match.

Ground truth (hardcoded; frozen from the served pages — the Heat and Knicks
met on January 23, March 15, April 5 and most recently on April 9, 2024):
    April 9, 2024: New York Knicks 102 @ Miami Heat 108 (Final, Kaseya Center;
    Heat won).  Top rebounder: Bam Adebayo 11 rebounds (Heat box score; Josh
    Hart 7 / Mitchell Robinson-side 9 for New York).

Checks: run-package gate + answer + navigation (team pages / game detail /
scoreboard) + final score 108-102 + both teams + Bam Adebayo 11 rebounds +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--23', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_heat_knicks",
            navigated_any(t, ["/miami-heat", "/new-york-knicks", "/game/25",
                              "/nba/scoreboard", "/nba/schedule", "/search"]),
            "must open the Heat/Knicks team pages, the game page, or search")
    j.check("answer_final_score", game_score_in(fa, 108, 102),
            "latest Heat-Knicks final: Heat 108, Knicks 102 (Apr 9, 2024)")
    j.check("answer_teams",
            contains_any(fa, ["heat", "miami"]) and
            contains_any(fa, ["knick", "new york"]),
            "both teams named")
    j.check("answer_top_rebounder",
            contains_any(fa, ["adebayo", "bam"]) and num_in(fa, 11),
            "top rebounder: Bam Adebayo, 11 rebounds")
    j.emit()

if __name__ == "__main__":
    main()
