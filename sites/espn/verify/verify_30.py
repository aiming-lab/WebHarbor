#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--30.

Check out the NHL Standings 2023-24 on ESPN to see which teams are at the top
and which are at the bottom in Eastern and Western Conference. What about the
situation in Division.

Ground truth (hardcoded; frozen from the served /nhl/standings page, which
groups the East into Atlantic / Metropolitan and the West into Central /
Pacific, each ordered by the displayed standing rank):
    Displayed division tops: Boston Bruins (Atlantic, 47-20-15), Carolina
    Hurricanes (Metropolitan, 52-23-7), Dallas Stars (Central, 52-21-9), Vegas
    Golden Knights (Pacific, 45-29-8).  Displayed division bottoms: Ottawa
    Senators, Washington Capitals, Chicago Blackhawks, Anaheim Ducks.  NOTE:
    the seeded display order contradicts the raw records (the Rangers 55-23-4
    own the East's best record, the Panthers/Canucks top the Atlantic/Pacific
    by record, the Blue Jackets/Sharks own the worst records), so the
    by-record reading (Rangers/Blue Jackets East, Stars/Sharks West,
    Panthers/Canucks division tops) is accepted alongside the displayed
    order.

Checks: run-package gate + answer + navigation to /nhl/standings + >=3 top
teams + >=2 bottom teams + >=2 division names + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--30', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nhl_standings", navigated_to(t, "/nhl/standings"),
            "the task targets the NHL Standings page")
    # tops: displayed division leaders (Bruins/Hurricanes/Stars/Golden Knights),
    # by-record conference leaders (Rangers/Stars), and by-record division
    # leaders (Panthers/Rangers/Stars/Canucks) are all accepted.
    tops = [contains_any(fa, ["bruin"]), contains_any(fa, ["hurricane", "carolina"]),
            contains_any(fa, ["star", "dallas"]), contains_any(fa, ["golden knights", "vegas"]),
            contains_any(fa, ["ranger"]), contains_any(fa, ["panther", "florida"]),
            contains_any(fa, ["canuck", "vancouver"])]
    # bottoms: displayed last rows (Senators/Capitals/Blackhawks/Ducks) and the
    # by-record worst teams (Blue Jackets/Sharks) are accepted.
    bottoms = [contains_any(fa, ["senator", "ottawa"]), contains_any(fa, ["capital", "washington"]),
               contains_any(fa, ["blackhawk", "chicago blackhawks"]), contains_any(fa, ["duck", "anaheim"]),
               contains_any(fa, ["blue jacket", "columbus"]), contains_any(fa, ["shark", "san jose"])]
    divisions = [contains_any(fa, ["atlantic"]), contains_any(fa, ["metropolitan"]),
                 contains_any(fa, ["central"]), contains_any(fa, ["pacific"])]
    j.check("answer_top_teams", sum(1 for x in tops if x) >= 3,
            f"top mentions={sum(1 for x in tops if x)}/7 "
            "(Bruins/Hurricanes/Stars/Golden Knights/Rangers/Panthers/Canucks)")
    j.check("answer_bottom_teams", sum(1 for x in bottoms if x) >= 2,
            f"bottom mentions={sum(1 for x in bottoms if x)}/6 "
            "(Senators/Capitals/Blackhawks/Ducks/Blue Jackets/Sharks)")
    j.check("answer_divisions", sum(1 for x in divisions if x) >= 2,
            f"division names={sum(1 for x in divisions if x)}/4 (Atlantic/Metropolitan/Central/Pacific)")
    j.emit()

if __name__ == "__main__":
    main()
