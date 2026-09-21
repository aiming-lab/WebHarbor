#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--10.

Check ESPN for the score and a brief recap of the latest college football
championship game.

Ground truth (hardcoded; frozen from the served /college-football/scoreboard
and game pages — the only college football game on the mirror is the 2024 CFP
National Championship):
    January 8, 2024, College Football Playoff National Championship (ESPN),
    Michigan Stadium: Washington Huskies 13 - Michigan Wolverines 34 (Final).
    Page recap: 'Michigan won their first national championship in decades,
    defeating Washington 34-13 in the College Football Playoff National
    Championship.'

Checks: run-package gate + answer + navigation (college football section /
game page) + both teams + the 34-13 score + a championship recap anchor +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, game_score_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--10', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_college_football",
            navigated_any(t, ["/college-football", "/ncaaf", "/game/23"]),
            "must open the College Football section or the championship game page")
    j.check("answer_teams",
            contains_any(fa, ["washington", "huskie", "husky"])
            and contains_any(fa, ["michigan", "wolverine"]),
            "championship teams: Washington Huskies and Michigan Wolverines")
    j.check("answer_score", game_score_in(fa, 34, 13),
            "final score: Michigan 34, Washington 13")
    j.check("answer_recap",
            contains_any(fa, ["national championship", "college football playoff",
                              "cfp", "first national championship"]),
            "recap must reference the national championship")
    j.emit()

if __name__ == "__main__":
    main()
