#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--20.

Find Tesla Destination Charger closest to the National Air and Space Museum.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The National Air and Space Museum place page's 'Charging nearby' section
    lists the Tesla Destination Chargers with distance pills: Tesla Destination
    Charger - CFA Plaza (525 8th St SE, 0.3 mi), Tesla Destination Charger -
    L'Enfant Plaza (480 L'Enfant Plaza SW, 0.4 mi), Tesla Destination Charger -
    The Wharf (0.7 mi), Tesla Destination Charger - Capital One Arena (0.8 mi).
    The closest Tesla Destination Charger is the CFA Plaza one at 0.3 mi.
    Source: /place/washington-dc-national-air-and-space-museum?nearby_category=charging.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Air and Space Museum page or a Tesla charger search | answer
  identifies the Tesla Destination Charger - CFA Plaza as the closest | read-
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
    j = Judge('Google Map--20', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_museum_or_tesla",
            visited_place(t, "washington-dc-national-air-and-space-museum")
            or navigated_to(t, "tesla") or navigated_phrase(t, "air and space"),
            "air and space museum page or tesla search in the trajectory")
    j.check("answer_cfa_plaza_charger", contains_any(fa, ["cfa"]),
            f"final={fa[:200]!r}")
    j.check("answer_tesla_destination_charger",
            contains_any(fa, ["tesla destination", "destination charger"]),
            f"final={fa[:200]!r}")
    j.check("answer_closest_evidence",
            contains_any(fa, ["0.3", "closest", "nearest"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
