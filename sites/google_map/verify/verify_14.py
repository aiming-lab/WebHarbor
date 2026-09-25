#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--14.

Find motorcycle parking near Radio City Music Hall.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Motorcycle parking facilities near Radio City Music Hall (W 50th St, anchor
    of the search) with mirror distance pills: Icon Parking - Midtown 6th Ave
    (150 W 50th St, 0.1 mi), GMC Park Plaza Garage (124 W 47th St, 0.1 mi),
    Rockefeller Plaza Motorcycle Parking Lot (30 Rockefeller Plaza, 0.1 mi),
    6th Ave Municipal Deck (1270 6th Ave, 0.2 mi), SP+ Parking 51st Street
    (48 W 51st St, 0.2 mi), Edison ParkFast 6th Ave (1280 6th Ave, 0.3 mi),
    Times Square Motorcycle Parking Corral (0.4 mi), Rockefeller Center Garage
    (0.4 mi), Bryant Park Motorcycle Parking Corral (0.5 mi), Central Park South
    Motorcycle Parking Deck (0.5 mi), Hell's Kitchen Motorcycle Parking (0.7 mi).
    Their pages list 'Motorcycle parking' among the amenities.
    Source: /search?q=motorcycle+parking+near+radio+city+music+hall&sort=distance + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a motorcycle-parking search near Radio City or a qualifying facility's
  page | answer names at least one motorcycle parking facility near Radio City
  | read-only DB
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
    j = Judge('Google Map--14', a.no_llm)
    t, fa = grade_common(j, a)
    MOTO = ["Icon Parking - Midtown 6th Ave", "GMC Park Plaza Garage",
           "Rockefeller Plaza Motorcycle Parking Lot", "6th Ave Municipal Deck",
           "SP+ Parking 51st Street", "Edison ParkFast 6th Ave",
           "Times Square Motorcycle Parking Corral", "Rockefeller Center Garage",
           "Bryant Park Motorcycle Parking Corral", "Central Park South Motorcycle Parking Deck",
           "Hell's Kitchen Motorcycle Parking"]
    MOTO_SLUGS = ["new-york-ny-icon-parking-midtown-motorcycles",
                  "new-york-ny-gmc-park-plaza-motorcycle-lot",
                  "new-york-ny-rockefeller-plaza-motorcycle-lot",
                  "ny-nyc-radio-city-deck-6th-ave",
                  "new-york-ny-sp-parking-51st-st-motorbikes",
                  "new-york-ny-edison-park-fast-6th-ave",
                  "new-york-ny-times-square-moto-corral",
                  "new-york-ny-rockefeller-center-motorcycle-parking",
                  "new-york-ny-bryant-park-moto-corral",
                  "new-york-ny-central-park-south-moto-deck",
                  "new-york-ny-hells-kitchen-moto-parking"]
    j.check("nav_motorcycle_parking_search",
            navigated_to(t, "motorcycle") or navigated_phrase(t, "radio city")
        or visited_any_place(t, MOTO_SLUGS),
            "motorcycle parking search near Radio City or a facility page in the trajectory")
    j.check("answer_names_motorcycle_facility", count_names(fa, MOTO) >= 1,
            f"matched={count_names(fa, MOTO)} final={fa[:200]!r}")
    j.check("answer_motorcycle_evidence",
            contains_any(fa, ["motorcycle", "motorbike", "moto "]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
