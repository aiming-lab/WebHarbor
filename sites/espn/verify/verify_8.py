#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--8.

Find information on ESPN about the top three scoring leaders in the NBA as of
the last day of the regular season, and note which teams they play for.

Ground truth (hardcoded; frozen from the served /nba/stats/leaders?stat=points
page, season 2023-24):
    1. Joel Embiid — 34.7 PPG — Philadelphia 76ers
    2. Luka Doncic — 33.9 PPG — Dallas Mavericks
    3. Giannis Antetokounmpo — 30.4 PPG — Milwaukee Bucks

Checks: run-package gate + answer + navigation to the NBA stats-leaders pages +
all three names with their PPG and teams + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--8', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_stat_leaders",
            navigated_any(t, ["/stats/leaders", "/nba/players", "/nba/statistics",
                              "/nba/stats"]),
            "must open the NBA stats leaders page")
    j.check("answer_embiid", contains_all(fa, ["embiid"]) and num_in(fa, 34.7),
            "No. 1: Joel Embiid 34.7 PPG")
    j.check("answer_doncic", contains_all(fa, ["doncic"]) and num_in(fa, 33.9),
            "No. 2: Luka Doncic 33.9 PPG")
    j.check("answer_giannis", contains_any(fa, ["giannis", "antetokounmpo"]) and num_in(fa, 30.4),
            "No. 3: Giannis Antetokounmpo 30.4 PPG")
    j.check("answer_teams",
            contains_any(fa, ["76er", "philadelphia", "sixers"])
            and contains_any(fa, ["maverick", "dallas"])
            and contains_any(fa, ["buck", "milwaukee"]),
            "teams: 76ers, Mavericks, Bucks")
    j.emit()

if __name__ == "__main__":
    main()
