#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--18.

Find a route between Chicago to Los Angeles, then print the route details.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Driving directions Chicago -> Los Angeles offer three alternatives: via
    I-80 W 1,742 miles ~1 d 5 h; via I-90 W 1,951 mi ~1 d 8 h; via I-70 W
    2,265 mi ~1 d 13 h. The primary route is via I-80 W with step-by-step
    details (Merge onto I-80 W heading away from Michigan 87 mi; continue for
    the long haul 581 mi; stop for fuel/rest; approach California...).
    'Printing the route details' maps to reporting the route summary and steps.
    Source: /directions?from=Chicago&to=Los+Angeles.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Chicago -> Los Angeles directions page | answer reports the route
  details: 1,742 miles via I-80 with the ~1 d 5 h driving duration | read-only
  DB
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, navigated_to, navigated_any, navigated_phrase,
                        visited_place, visited_any_place, name_in, count_names,
                        contains_all, contains_any, distance_claim, minutes_claim,
                        number_claim, rating_order_ok, extract_mi_values, numbers_in)

def main():
    a = parse_args()
    j = Judge('Google Map--18', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_chicago_la_directions",
            navigated_to(t, "/directions") and navigated_to(t, "chicago")
            and navigated_to(t, "angeles"),
            "chicago->LA directions URL in the trajectory")
    j.check("answer_distance_1742_mi", distance_claim(fa, 1742), f"final={fa[:200]!r}")
    j.check("answer_route_via_i80", contains_any(fa, ["i-80"]), f"final={fa[:200]!r}")
    j.check("answer_duration_evidence",
            contains_any(fa, ["1 d 5", "1 day 5", "29 hour", "29 h", "29-hour", "d 5 h"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
