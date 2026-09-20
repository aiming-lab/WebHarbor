#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--24.

Find a Barcelona hotel for Feb 25-28 2024; sort the results by distance from
the beach; they must offer free WiFi and breakfast.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Barcelona properties with free WiFi and breakfast included (4): Praktik
    Essens (0.8 mi from Barceloneta Beach), Acta Voraport (1.0), Hotel Brick
    Barcelona (1.4), Seventy Barcelona (1.9).

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
    "Seventy Barcelona": [
        "Seventy Barcelona"
    ],
    "Acta Voraport": [
        "Acta Voraport"
    ],
    "Hotel Brick Barcelona": [
        "Hotel Brick Barcelona"
    ],
    "Praktik Èssens": [
        "Praktik Essens",
        "Praktik Èssens"
    ]
}
SLUGS = ["seventy-barcelona-barcelona", "acta-voraport-barcelona", "hotel-brick-barcelona-barcelona", "praktik-èssens-barcelona"]


def main():
    a = parse_args()
    j = Judge('Booking--24', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_barcelona_beach_sort",
            (search_url_with(t, ["barcelona"]) and search_url_with(t, ["sort=distance_beach"]))
            or (search_url_with(t, ["barcelona", "wifi=1"]) and search_url_with(t, ["breakfast=1"])),
            "Barcelona results with the beach-distance sort (and WiFi/breakfast filters)")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
