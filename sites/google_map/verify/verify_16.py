#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--16.

Find EV charging supported parking closest to Smithsonian museum.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Anchoring the search on 'smithsonian' (Smithsonian Institution, 1000 Jefferson
    Dr SW), the EV-charging-supported parking facilities and their distance pills:
    Smithsonian Castle Garage (600 Maryland Ave SW, 'Rapid charging stations
    available on Level 2', amenities include ev charging) 0.2 mi, Air & Space EV
    Parking Deck (650 Independence Ave SW, 'EV charging stations' amenity) 0.2 mi,
    National Mall East EV Parking Garage 0.4 mi, EVgo Fast Charger - Mall South 0.5 mi.
    Natural History Museum Lot (0.0 mi) has NO EV charging amenity and does not qualify.
    The two closest EV-charging lots display a tied 0.2 mi; the verifier accepts either.
    Source: /search?q=ev+charging+parking+near+smithsonian&sort=distance + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Smithsonian-anchored EV-parking search or a qualifying garage's page
  | answer names Smithsonian Castle Garage or Air & Space EV Parking Deck with
  EV-charging evidence | read-only DB
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
    j = Judge('Google Map--16', a.no_llm)
    t, fa = grade_common(j, a)
    CLOSEST_EV_PARKING = ["Smithsonian Castle Garage", "Air & Space EV Parking Deck"]
    EV_SLUGS = ["washington-dc-smithsonian-ev-charging-garage", "washington-dc-air-space-ev-deck"]
    j.check("nav_smithsonian_ev_search",
            navigated_to(t, "smithsonian") or visited_any_place(t, EV_SLUGS),
            "smithsonian EV parking search or a qualifying garage page in the trajectory")
    j.check("answer_names_closest_ev_parking", count_names(fa, CLOSEST_EV_PARKING) >= 1,
            f"matched={count_names(fa, CLOSEST_EV_PARKING)} final={fa[:200]!r}")
    j.check("answer_ev_charging_evidence",
            contains_any(fa, ["ev charging", "charging stations", "charging"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
