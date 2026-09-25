#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--13.

Find a parking lot in Gloucester and book a ride from there to North Plymouth, view the map to understand the route better.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Gloucester parking: Gloucester Waterfront Parking (1 Harbor Loop, Gloucester,
    MA 01930, Mon-Sun 6:00 AM - 10:00 PM) and Main St Municipal Lot Gloucester
    (169 Main St, Gloucester, MA 01930, 9:00 AM - 9:00 PM).
    Directions from either lot to North Plymouth, MA (driving): primary route via
    I-93, 45.0 miles, about 54 minutes (alternatives via I-90 ~50 mi / 1 h and via
    US-1 ~58 mi / 1 h 10 min); the route map and step-by-step details render on the
    directions page. 'Booking a ride' maps to the mirror's directions feature.
    Source: /search?q=parking+in+gloucester and /directions?from=<lot>&to=North+Plymouth.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Gloucester parking search/page AND the Gloucester -> North Plymouth
  directions page | answer names a Gloucester parking lot and reports the 45.0
  mi ~54 min via I-93 route | read-only DB
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
    j = Judge('Google Map--13', a.no_llm)
    t, fa = grade_common(j, a)
    GLOUCESTER_LOTS = ["Gloucester Waterfront Parking", "Main St Municipal Lot Gloucester"]
    j.check("nav_gloucester_parking", navigated_to(t, "gloucester"),
            "gloucester search or directions URL in the trajectory")
    j.check("nav_directions_to_plymouth",
            navigated_to(t, "/directions") and navigated_to(t, "plymouth"),
            "directions URL toward Plymouth in the trajectory")
    j.check("answer_names_gloucester_lot", count_names(fa, GLOUCESTER_LOTS) >= 1,
            f"matched={count_names(fa, GLOUCESTER_LOTS)} final={fa[:200]!r}")
    j.check("answer_route_via_i93", contains_any(fa, ["i-93"]), f"final={fa[:200]!r}")
    j.check("answer_route_45_mi", distance_claim(fa, 45.0), f"final={fa[:200]!r}")
    j.check("answer_route_54_min", minutes_claim(fa, 54), f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
