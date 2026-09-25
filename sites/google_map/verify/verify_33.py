#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--33.

Check out Denver International Airport's information and tell me: 1) which level has the least proportion in reviews; 2) what are its Accessibility and Amenities.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Denver International Airport's place page (8500 Peña Blvd, 4.3 stars,
    38,400 reviews) shows 12 visible reviews whose star levels distribute as
    5-star: 4, 4-star: 3, 3-star: 2, 2-star: 1, 1-star: 2 - so the 2-star level
    has the least proportion (one review: 'Ticketing area is confusing for
    first-time flyers.'). Accessibility: Wheelchair accessible. Amenities:
    Parking, Free Wi-Fi, Restrooms, Shops, Restaurants, Train to city,
    Pet relief area.
    Source: /place/denver-co-denver-international-airport.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Denver International Airport place page | answer identifies the
  2-star level as least represented, and reports the Accessibility and at
  least three Amenities | read-only DB
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
    j = Judge('Google Map--33', a.no_llm)
    t, fa = grade_common(j, a)
    AMENITY_TOKENS = ["parking", "free wi-fi", "wifi", "restrooms", "shops",
                   "restaurants", "train", "pet relief"]
    j.check("nav_denver_airport_page",
            visited_place(t, "denver-co-denver-international-airport")
            or navigated_to(t, "denver international"),
            "denver international airport page or search in the trajectory")
    j.check("answer_least_proportion_level",
            contains_any(fa, ["2-star", "2 star", "two-star", "two star"]),
            f"final={fa[:200]!r}")
    matched_amenities = sum(1 for tok in AMENITY_TOKENS if contains_any(fa, [tok]))
    j.check("answer_amenities", matched_amenities >= 3,
            f"matched={matched_amenities} final={fa[:250]!r}")
    j.check("answer_accessibility", contains_any(fa, ["wheelchair"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
