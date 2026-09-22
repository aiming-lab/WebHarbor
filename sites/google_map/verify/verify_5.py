#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--5.

Search for a parking garage near Thalia Hall in Chicago that isn't open 24 hours.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Thalia Hall (1807 S Allport St, Chicago) anchors the parking search. The
    non-24-hour parking facilities near it are: 18th Street Parking (1801 S Racine
    Ave, Mon-Sun 7:00 AM - 11:00 PM, 2.4 mi), Racine Ave Parking (1810 S Racine Ave,
    8:00 AM - 10:00 PM, 2.5 mi), Pilsen Garage (1820 S Allport St, 6:00 AM - 1:00 AM,
    2.2 mi), Allport Garage (1900 S Allport St, 7:00 AM - 12:00 AM, 2.3 mi),
    Lower West Side Lot (1700 W 18th St, 6:00 AM - 11:00 PM, 2.1 mi).
    The 24-hour facilities (Blue Island Avenue Garage, Pilsen North Garage,
    Pilsen Center Garage, Halsted Street Lot, Pilsen Residents Lot) do NOT qualify.
    Source: /search?q=parking+near+thalia+hall+chicago (14 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Thalia Hall parking search or a qualifying lot's place page | answer
  names a non-24h lot and reports its daytime closing hours | read-only DB
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
    j = Judge('Google Map--5', a.no_llm)
    t, fa = grade_common(j, a)
    LOTS = ["18th Street Parking", "Racine Ave Parking", "Pilsen Garage",
           "Allport Garage", "Lower West Side Lot"]
    LOT_SLUGS = ["chicago-il-18th-street-parking", "chicago-il-racine-ave-parking",
                 "chicago-il-pilsen-garage", "chicago-il-allport-garage",
                 "chicago-il-lower-west-side-lot"]
    j.check("nav_thalia_parking_search",
            navigated_to(t, "thalia") or visited_any_place(t, LOT_SLUGS),
            "thalia hall parking search or a qualifying lot page in the trajectory")
    j.check("answer_names_non_24h_lot", count_names(fa, LOTS) >= 1,
            f"matched={count_names(fa, LOTS)} final={fa[:200]!r}")
    j.check("answer_daytime_hours_evidence",
            contains_any(fa, ["pm", "not open 24", "not 24-hour", "not 24 hours",
                              "isn't open 24", "closes", "closed at night"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
