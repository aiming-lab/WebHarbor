#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--0.

Look up the current standings for the NBA Eastern Conference on ESPN.

Ground truth (hardcoded; frozen from the served mirror pages — the /nba/standings
page lists the East grouped by Atlantic / Central / Southeast):
    Atlantic: Boston Celtics 64-18, New York Knicks 50-32, Philadelphia 76ers
    47-35, Toronto Raptors 25-57, Brooklyn Nets 32-50.  Central: Cleveland
    Cavaliers 48-34, Indiana Pacers 47-35, Milwaukee Bucks 49-33, Chicago Bulls
    39-43, Detroit Pistons 14-68.  Southeast: Miami Heat 46-36, Orlando Magic
    47-35, Atlanta Hawks 36-46, Washington Wizards 15-67, Charlotte Hornets
    21-61.

Checks: run-package gate + non-empty answer + navigation to /nba/standings +
the East's best record (Celtics 64-18) + breadth (>=6 East teams reported) +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        num_in, Judge, parse_args)

EAST_TEAMS = ["boston celtics", "new york knicks", "philadelphia 76ers",
              "toronto raptors", "brooklyn nets", "cleveland cavaliers",
              "indiana pacers", "milwaukee bucks", "chicago bulls",
              "detroit pistons", "miami heat", "orlando magic",
              "atlanta hawks", "washington wizards", "charlotte hornets"]

def main():
    a = parse_args()
    j = Judge('ESPN--0', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nba_standings", navigated_to(t, "/nba/standings"),
            "the task requires the NBA standings page")
    j.check("answer_celtics_best_record",
            contains_any(fa, ["celtics", "boston"]) and num_in(fa, 64) and num_in(fa, 18),
            "Eastern Conference best record: Celtics 64-18")
    east = [tm for tm in EAST_TEAMS if tm in fa.lower()]
    j.check("answer_east_breadth", len(east) >= 6,
            f"east teams reported={len(east)}: {east}")
    j.emit()

if __name__ == "__main__":
    main()
