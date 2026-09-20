#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--39.

Find a route from Miami to New Orleans, and provide the detailed route information.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Driving directions Miami, FL -> New Orleans, LA offer three alternatives:
    via I-95 669 miles ~11 h 9 min; via I-75 749 mi ~12 h 29 min; via I-4 870 mi
    ~14 h 30 min. The primary route is via I-95 with step-by-step details
    (Merge onto I-95 heading away of Florida 33 mi; continue for the long haul
    223 mi; stop for fuel/rest; approach Louisiana...).
    Source: /directions?from=Miami&to=New+Orleans.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Miami -> New Orleans directions page | answer reports the route
  details: 669 miles via I-95 with the ~11 h 9 min driving duration | read-
  only DB
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
    j = Judge('Google Map--39', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_miami_new_orleans",
            navigated_to(t, "/directions") and navigated_to(t, "miami")
            and navigated_to(t, "orleans"),
            "miami->new orleans directions URL in the trajectory")
    j.check("answer_distance_669_mi", distance_claim(fa, 669), f"final={fa[:200]!r}")
    j.check("answer_route_via_i95", contains_any(fa, ["i-95"]), f"final={fa[:200]!r}")
    j.check("answer_duration_evidence",
            contains_any(fa, ["11 h 9", "11 hours 9", "11 hr", "11 h", "11h",
                              "11 hours", "eleven hours"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
