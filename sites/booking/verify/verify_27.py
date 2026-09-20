#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--27.

Find a Melbourne hotel offering free parking and free WiFi, Feb 28 - Mar 4
2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Melbourne properties with parking and WiFi (7 qualify).

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
    "The Langham Melbourne": [
        "The Langham Melbourne"
    ],
    "Crown Towers Melbourne": [
        "Crown Towers Melbourne"
    ],
    "Novotel Melbourne": [
        "Novotel Melbourne"
    ],
    "Hotel Lindrum Melbourne": [
        "Hotel Lindrum Melbourne"
    ],
    "Pan Pacific Melbourne South Wharf": [
        "Pan Pacific Melbourne South Wharf"
    ],
    "Tribe Hotel Melbourne": [
        "Tribe Hotel Melbourne"
    ],
    "Adina Apartment Hotel Melbourne": [
        "Adina Apartment Hotel Melbourne"
    ]
}
SLUGS = ["the-langham-melbourne-melbourne", "crown-towers-melbourne-melbourne", "novotel-melbourne-melbourne", "hotel-lindrum-melbourne-melbourne", "pan-pacific-melbourne-south-wharf-melbourne", "tribe-hotel-melbourne-melbourne", "adina-apartment-hotel-melbourne-melbourne"]


def main():
    a = parse_args()
    j = Judge('Booking--27', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_melbourne_parking_wifi",
            (search_url_with(t, ["melbourne", "parking=1"]) and search_url_with(t, ["wifi=1"]))
            or any(visited_property(t, s) for s in SLUGS),
            "Melbourne results with the parking/WiFi filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
