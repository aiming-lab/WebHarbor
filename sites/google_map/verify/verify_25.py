#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--25.

Search for a parking facility near the Fox Theater in Detroit that closes at night.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Parking facilities near the Fox Theatre Detroit (2211 Woodward Ave) with
    non-24-hour hours: Fox Theatre Garage (Mon-Sun 7:00 AM - 12:00 AM, 0.8 mi,
    closes at midnight), Grand Circus Parking (7:00 AM - 11:00 PM, 1.4 mi),
    Cass Park Lot (8:00 AM - 12:00 AM, 1.0 mi). The 24-hour facilities (Foxtown
    Garage, Comerica Park overnight lot) do NOT qualify. There is also a second
    'Comerica Park Lot' (6:00 AM - 11:00 PM, 1.1 mi) whose name collides with the
    24h 'Comerica Park Lot' (0.5 mi), so only unambiguous names are accepted.
    Source: /search?q=parking+near+fox+theater+detroit (28 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Fox Theatre parking search or a qualifying facility's page | answer
  names a facility that closes at night with closing-hours evidence | read-
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
    j = Judge('Google Map--25', a.no_llm)
    t, fa = grade_common(j, a)
    LOTS = ["Fox Theatre Garage", "Grand Circus Parking", "Cass Park Lot"]
    LOT_SLUGS = ["detroit-mi-fox-theatre-garage", "detroit-mi-grand-circus-parking",
                 "detroit-mi-cass-park-evening-lot"]
    j.check("nav_fox_theatre_parking",
            navigated_phrase(t, "fox theater") or navigated_phrase(t, "fox theatre")
        or visited_any_place(t, LOT_SLUGS),
            "fox theatre parking search or a qualifying lot page in the trajectory")
    j.check("answer_names_closing_lot", count_names(fa, LOTS) >= 1,
            f"matched={count_names(fa, LOTS)} final={fa[:200]!r}")
    j.check("answer_closes_at_night_evidence",
            contains_any(fa, ["pm", "closes", "closed at", "midnight", "not 24",
                              "not open 24", "at night"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
