#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--24.

Plan a journey from San Francisco International Airport to Union Square via driving.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The bare endpoint 'Union Square' is ambiguous (8 matches) and resolves to
    'Union Square San Francisco' (333 Post St). Driving directions from San
    Francisco International Airport (San Francisco, CA 94128) offer three
    alternatives: via I-5 11.6 mi ~22 min, via US-101 13.0 mi ~24 min, via
    I-405 15.1 mi ~28 min. The primary route is via I-5: 11.6 miles, ~22 minutes.
    Source: /directions?from=San+Francisco+International+Airport&to=Union+Square+San+Francisco&mode=driving.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: driving directions SFO -> Union Square (San Francisco) | answer reports
  the driving route: 11.6 mi, ~22 min, via I-5 | read-only DB
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
    j = Judge('Google Map--24', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_sfo_union_square",
            navigated_to(t, "/directions") and navigated_phrase(t, "san francisco international")
            and navigated_phrase(t, "union square"),
            "SFO->Union Square directions URL in the trajectory")
    j.check("answer_distance_11_6_mi", distance_claim(fa, 11.6), f"final={fa[:200]!r}")
    j.check("answer_duration_22_min", minutes_claim(fa, 22), f"final={fa[:200]!r}")
    j.check("answer_route_via_i5", contains_any(fa, ["i-5"]), f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
