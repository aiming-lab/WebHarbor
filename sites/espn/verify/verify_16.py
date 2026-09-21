#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--16.

Check the schedule for the NBA game on December 25, 2023, and provide the
teams that are playing and their current standings in their respective
conferences.

Ground truth (hardcoded; frozen from the served pages — the December 25, 2023
scoreboard lists the Lakers-Celtics game first, and /nba/standings gives the
current records):
    December 25, 2023: Boston Celtics @ Los Angeles Lakers (first Christmas
    game listed; Lakers won 120-117).  Current standings: Boston Celtics
    64-18 (.780), 1st in the East (Atlantic); Los Angeles Lakers 47-35
    (.573), Western Conference (Pacific).

Checks: run-package gate + answer + navigation (dated scoreboard / schedule /
standings / the two team pages) + both teams + both conference records +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--16', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_dated_or_standings",
            navigated_any(t, ["20231225", "/nba/standings", "/los-angeles-lakers",
                              "/boston-celtics", "/nba/schedule"]),
            "must open the dated scoreboard/schedule, the standings, or the team pages")
    j.check("answer_teams",
            contains_any(fa, ["laker", "los angeles"]) and
            contains_any(fa, ["celtic", "boston"]),
            "the December 25 game: Lakers vs Celtics")
    celtics_rec = (num_in(fa, 64) and num_in(fa, 18)) or contains_any(fa, [".780", "780"])
    lakers_rec = (num_in(fa, 47) and num_in(fa, 35)) or contains_any(fa, [".573", "573"])
    j.check("answer_standings", celtics_rec and lakers_rec,
            "current records: Celtics 64-18 (.780) and Lakers 47-35 (.573)")
    j.emit()

if __name__ == "__main__":
    main()
