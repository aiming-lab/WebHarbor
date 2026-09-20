#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--38.

Look up Vienna hotel options with parking, breakfast included and 8+ rating,
for a 4-night stay Feb 28 - Mar 4 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Vienna properties with parking, breakfast and rating >= 8.0 (4):
    Hotel Schani UNO City, Hotel Indigo Vienna - Naschmarkt by IHG, Hotel Josefine, Superbude Wien Prater.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)

ALLOWED = {
    "Hotel Schani UNO City": [
        "Hotel Schani UNO City"
    ],
    "Hotel Indigo Vienna - Naschmarkt by IHG": [
        "Hotel Indigo Vienna - Naschmarkt by IHG"
    ],
    "Hotel Josefine": [
        "Hotel Josefine"
    ],
    "Superbude Wien Prater": [
        "Superbude Wien Prater"
    ]
}
SLUGS = ["hotel-schani-uno-city-vienna", "hotel-indigo-vienna-naschmarkt-by-ihg-vienna", "hotel-josefine-vienna", "superbude-wien-prater-vienna"]


def main():
    a = parse_args()
    j = Judge('Booking--38', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_vienna_parking_bkf_8",
            (search_url_with(t, ["vienna", "parking=1"]) and search_url_with(t, ["breakfast=1"])
             and search_url_with(t, ["min_rating=8"]))
            or any(visited_property(t, s) for s in SLUGS),
            "Vienna results with the parking/breakfast/8+ filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
