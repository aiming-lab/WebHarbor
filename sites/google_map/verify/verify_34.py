#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--34.

Find a hiking trail within 2 miles of zip code 80202.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Hiking trails within 2 miles of the 80202 zip centroid (Denver): Highland
    Canal Trail (0.0 mi), Cherry Creek Trail (0.2 mi), South Platte River Trail
    (0.2 mi), Commons Park Loop Trail (0.2 mi), City Park Loop (0.3 mi),
    Confluence Park Loop (0.6 mi). Sloan's Lake Trail (2.9 mi), Washington Park
    Loop (3.8 mi), Ruby Hill Park Trail (4.2 mi) and Red Rocks Trail (9.6 mi)
    are outside the radius.
    Source: /search?q=hiking+trail+near+80202 (10 results with distance pills).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a hiking-trail search near 80202 or a qualifying trail's page | answer
  names a qualifying trail with distance evidence of 2 miles or less | read-
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
    j = Judge('Google Map--34', a.no_llm)
    t, fa = grade_common(j, a)
    TRAILS = ["Highland Canal Trail", "Cherry Creek Trail", "South Platte River Trail",
             "Commons Park Loop Trail", "City Park Loop", "Confluence Park Loop"]
    TRAIL_SLUGS = ["denver-co-highland-canal-trail", "denver-co-cherry-creek-trail",
                   "denver-co-south-platte-river-trail", "denver-co-commons-park-loop-trail",
                   "denver-co-city-park-loop", "denver-co-confluence-park-loop"]
    j.check("nav_trail_search",
            navigated_any(t, ["80202", "hiking", "trail"]) or visited_any_place(t, TRAIL_SLUGS),
            "hiking trail search near 80202 or a trail page in the trajectory")
    j.check("answer_names_qualifying_trail", count_names(fa, TRAILS) >= 1,
            f"matched={count_names(fa, TRAILS)} final={fa[:200]!r}")
    mi_vals = extract_mi_values(fa)
    j.check("answer_within_2_miles",
            any(v <= 2.0 for v in mi_vals)
            or contains_any(fa, ["within 2 miles", "within 2 mi", "within two miles",
                                 "under 2 miles", "less than 2 miles", "2 miles or less"]),
            f"mi_values={mi_vals} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
