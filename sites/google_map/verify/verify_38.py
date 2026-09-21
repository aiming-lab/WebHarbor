#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--38.

Search for bicycle parking near the Empire State Building.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Bicycle parking facilities near the Empire State Building (350 5th Ave,
    anchor of the search) with mirror distance pills: 34th Street DOT Bike
    Corral (0.1 mi), Koreatown Bike Parking Corral (0.1 mi), Herald Square Bike
    Parking Rack (0.2 mi), 34th Street Transit Plaza (0.2 mi), Bryant Park Bike
    Parking Station (0.4 mi), Fifth Avenue Parking Corral (0.5 mi), Madison
    Square Park Bike Parking Corral (0.5 mi). Their pages list 'Bicycle parking'
    among the amenities (U-rack / post-and-ring).
    Source: /search?q=bicycle+parking+near+empire+state+building&sort=distance (51 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a bicycle-parking search near the Empire State Building or a facility's
  page | answer names at least one bicycle parking facility | read-only DB
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
    j = Judge('Google Map--38', a.no_llm)
    t, fa = grade_common(j, a)
    BIKES = ["34th Street DOT Bike Corral", "Koreatown Bike Parking Corral",
            "Herald Square Bike Parking Rack", "34th Street Transit Plaza",
            "Bryant Park Bike Parking Station", "Fifth Avenue Parking Corral",
            "Madison Square Park Bike Parking Corral"]
    BIKE_SLUGS = ["new-york-ny-empire-state-bike-corral", "new-york-ny-koreatown-bike-corral",
                  "new-york-ny-herald-square-bike-rack", "new-york-ny-empire-state-bike-rack",
                  "new-york-ny-bryant-park-bike-station", "new-york-ny-34th-st-bicycle-parking",
                  "new-york-ny-madison-square-park-bike-corral"]
    j.check("nav_bicycle_parking_search",
            navigated_any(t, ["bicycle", "bike"]) or visited_any_place(t, BIKE_SLUGS),
            "bicycle parking search near the Empire State Building or a facility page in the trajectory")
    j.check("answer_names_bicycle_facility", count_names(fa, BIKES) >= 1,
            f"matched={count_names(fa, BIKES)} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
