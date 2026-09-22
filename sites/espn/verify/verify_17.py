#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--17.

Check out the NBA Basketball Power Index 2023-24 to see which teams are in
first place and which are in last place.

Ground truth (hardcoded; frozen from the served /nba/bpi page):
    No. 1: Boston Celtics — BPI 10.5 (99.2% playoff odds, +7.1, 64-18).
    No. 30 (last): San Antonio Spurs — BPI 0.9 (8.0%, -4.5, 22-60).

Checks: run-package gate + answer + navigation to /nba/bpi + first-place
Celtics with BPI 10.5 + last-place Spurs with BPI 0.9 + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--17', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_bpi", navigated_to(t, "/nba/bpi"),
            "the task targets the NBA Basketball Power Index page")
    j.check("answer_first_celtics",
            contains_any(fa, ["celtic", "boston"]) and num_in(fa, 10.5),
            "first place: Boston Celtics, BPI 10.5")
    j.check("answer_last_spurs",
            contains_any(fa, ["spur", "san antonio"]) and num_in(fa, 0.9),
            "last place: San Antonio Spurs, BPI 0.9")
    j.emit()

if __name__ == "__main__":
    main()
