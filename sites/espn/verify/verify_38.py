#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--38.

Check Los Angeles Lakers Stats 2023-24, calculate Anthony Davis' games played
(GP) percentage, tell me if there are other players with the same games played
percentage as Anthony Davis.

Ground truth (hardcoded; frozen from the served
/team/nba/los-angeles-lakers/stats page):
    Anthony Davis PF — GP 76 (of the 82-game season -> 92.7%).  Two other
    Lakers played exactly 76 games: Austin Reaves (SG, 76) and D'Angelo
    Russell (PG, 76) — so YES, other players share Davis' GP percentage.

Checks: run-package gate + answer + navigation to the Lakers stats page +
Davis' 76 GP + a correct percentage claim + Reaves and/or Russell named as the
matching players + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        num_in, norm, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--38', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lakers_stats", navigated_to(t, "/team/nba/los-angeles-lakers/stats"),
            "the task names the Lakers Stats page")
    j.check("answer_davis_gp", num_in(fa, 76),
            "Anthony Davis played 76 games")
    f = norm(fa)
    pct = ("92.7" in f) or ("92.68" in f) or ("0.927" in f) or (".927" in f) \
        or ("76/82" in f) or ("76 of 82" in f) or ("76 out of 82" in f) \
        or ("93%" in f) or ("93 percent" in f) or ("~93" in f) or ("93.0%" in f)
    j.check("answer_gp_percentage", pct,
            "GP percentage: 76/82 = 92.7%")
    j.check("answer_same_gp_players",
            contains_any(fa, ["reaves"]) or contains_any(fa, ["russell", "d'angelo"]),
            "Austin Reaves and D'Angelo Russell also played 76 games")
    j.emit()

if __name__ == "__main__":
    main()
