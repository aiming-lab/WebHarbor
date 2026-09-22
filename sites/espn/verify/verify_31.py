#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--31.

Who has the heaviest weight among infielders in the New York Yankees Roster
2023-24?

Ground truth (hardcoded; frozen from the served /team/mlb/new-york-yankees/roster
page — infielder weights: Rizzo (1B) 240 lbs, Gleyber Torres (2B) 205,
LeMahieu (3B) 215, Trevino (C) 215, Austin Wells (C) 220, Jon Berti (3B) 195,
Oswaldo Cabrera (3B) 215, Jahmai Jones (2B) 200, Kevin Smith (3B) 200,
Oswald Peraza (2B) 184):
    Anthony Rizzo (1B), 240 lbs, is the heaviest infielder.  (Giancarlo
    Stanton, 245 lbs, is listed as DH, not an infielder.)

Checks: run-package gate + answer + navigation (Yankees roster page or the
Yankees preview article) + Rizzo named with 240 lbs + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, contains_all,
                        contains_any, num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--31', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_yankees_roster",
            navigated_any(t, ["/team/mlb/new-york-yankees/roster",
                              "/team/mlb/new-york-yankees", "/story/yankees"]),
            "must open the Yankees roster page (or the Yankees preview article)")
    j.check("answer_rizzo", contains_any(fa, ["rizzo"]),
            "heaviest infielder: Anthony Rizzo")
    j.check("answer_weight", num_in(fa, 240),
            "Rizzo weighs 240 lbs")
    j.emit()

if __name__ == "__main__":
    main()
