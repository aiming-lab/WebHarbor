#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--37.

Locate a parking area in Salem and find a route from there to Marblehead, including map directions for better understanding.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Salem parking areas: Salem Waterfront Parking (10 Blaney St, Salem, MA
    01970, Mon-Sun 6:00 AM - 11:00 PM, 0.2 mi) and Museum Place Mall Parking
    Salem (1 E India Sq Mall, Salem, MA 01970, 9:00 AM - 9:00 PM, 0.1 mi).
    Driving directions to Marblehead, MA: from Salem Waterfront Parking via I-93
    2.3 mi ~6 min (alternatives 2.5 mi ~7 min via I-90, 2.9 mi ~8 min via US-1);
    from Museum Place Mall Parking via I-93 2.5 mi ~7 min (alternatives 2.7 mi
    ~7 min via I-90, 3.2 mi ~9 min via US-1). The directions page renders the
    route map and step-by-step details.
    Source: /search?q=parking+in+salem+ma and /directions?from=<lot>&to=Marblehead.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Salem parking search/page AND the Salem -> Marblehead directions page
  | answer names a Salem parking area and reports its route to Marblehead (via
  I-93, 2.3 mi ~6 min or 2.5 mi ~7 min) | read-only DB
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
    j = Judge('Google Map--37', a.no_llm)
    t, fa = grade_common(j, a)
    SALEM_LOTS = ["Salem Waterfront Parking", "Museum Place Mall Parking Salem"]
    j.check("nav_salem_parking", navigated_to(t, "salem"),
            "salem parking search or directions URL in the trajectory")
    j.check("nav_directions_to_marblehead",
            navigated_to(t, "/directions") and navigated_to(t, "marblehead"),
            "salem->marblehead directions URL in the trajectory")
    j.check("answer_names_salem_parking", count_names(fa, SALEM_LOTS) >= 1,
            f"matched={count_names(fa, SALEM_LOTS)} final={fa[:200]!r}")
    j.check("answer_route_via_i93", contains_any(fa, ["i-93"]), f"final={fa[:200]!r}")
    j.check("answer_route_numbers",
            (distance_claim(fa, 2.3) and minutes_claim(fa, 6))
            or (distance_claim(fa, 2.5) and minutes_claim(fa, 7)),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
