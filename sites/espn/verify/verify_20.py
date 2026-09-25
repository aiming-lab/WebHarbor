#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--20.

Look up the current leaders in rebounds and assists in the NBA Western
Conference on ESPN.

Ground truth (hardcoded; frozen from the served
/nba/stats/leaders?stat=rebounds&conference=West and
...?stat=assists&conference=West pages, season 2023-24):
    Western Conference rebounds leader: Domantas Sabonis (Sacramento Kings)
    13.6 RPG.  Western Conference assists leader: Luka Doncic (Dallas
    Mavericks) 9.8 APG.

Checks: run-package gate + answer + navigation with a conference=West filter +
Sabonis 13.6 + Doncic 9.8 + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--20', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_west_filter", navigated_to(t, "conference=west"),
            "the leaders must be filtered to the Western Conference")
    j.check("answer_rebounds_leader",
            contains_all(fa, ["sabonis"]) and num_in(fa, 13.6),
            "West rebounds leader: Domantas Sabonis 13.6")
    j.check("answer_assists_leader",
            contains_any(fa, ["doncic", "luka"]) and num_in(fa, 9.8),
            "West assists leader: Luka Doncic 9.8")
    j.emit()

if __name__ == "__main__":
    main()
