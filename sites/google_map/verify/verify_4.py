#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--4.

Plan a trip from Boston Logan Airport to North Station.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Driving directions from Boston Logan International Airport (1 Harborside
    Drive) to North Station (135 Causeway St) offer three alternatives:
    via I-93 2.7 mi ~7 min, via I-90 (Mass Pike) 3.1 mi ~8 min, via US-1 3.6 mi ~10 min.
    The primary/fastest route is via I-93: 2.7 miles, about 7 minutes.
    Source: /directions?from=Boston+Logan+Airport&to=North+Station.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: directions Boston Logan Airport -> North Station | answer reports the
  route with 2.7 mi, ~7 min, via I-93 | read-only DB
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
    j = Judge('Google Map--4', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_logan_to_north_station",
            navigated_to(t, "/directions") and navigated_to(t, "logan")
            and navigated_phrase(t, "north station"),
            "directions URL from Logan to North Station in the trajectory")
    j.check("answer_route_via_i93", contains_any(fa, ["i-93"]), f"final={fa[:200]!r}")
    j.check("answer_distance_2_7_mi", distance_claim(fa, 2.7), f"final={fa[:200]!r}")
    j.check("answer_duration_7_min", minutes_claim(fa, 7), f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
