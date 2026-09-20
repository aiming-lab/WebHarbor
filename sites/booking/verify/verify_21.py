#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--21.

Find a Sydney hotel with rating 8+, free WiFi and parking, four nights from
March 10, 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Sydney properties with rating >= 8.0, free WiFi and parking (3): Wildlife
    Retreat at Taronga, The Grand National Hotel by Saint Peter, Paramount
    House Hotel.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, contains_affirmative,
                        mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)

ALLOWED = {
    "Wildlife Retreat at Taronga": [
        "Wildlife Retreat at Taronga"
    ],
    "The Grand National Hotel by Saint Peter": [
        "The Grand National Hotel by Saint Peter"
    ],
    "Paramount House Hotel": [
        "Paramount House Hotel"
    ]
}
SLUGS = ["wildlife-retreat-at-taronga-sydney", "the-grand-national-hotel-by-saint-peter-sydney", "paramount-house-hotel-sydney"]


def main():
    a = parse_args()
    j = Judge('Booking--21', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_sydney_8_wifi_parking",
            (search_url_with(t, ["sydney", "min_rating=8"])
             and search_url_with(t, ["wifi=1"]) and search_url_with(t, ["parking=1"]))
            or any(visited_property(t, s) for s in SLUGS),
            "Sydney results with the 8+/WiFi/parking filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
