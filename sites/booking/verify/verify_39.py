#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--39.

Find a pet-friendly hotel with parking available in downtown Toronto for
February 24-26 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Toronto pet-friendly properties with parking (4):
    Four Seasons Hotel Toronto, Fairmont Royal York Toronto, The Ritz-Carlton Toronto, 1 Hotel Toronto.

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
    "Four Seasons Hotel Toronto": [
        "Four Seasons Hotel Toronto"
    ],
    "Fairmont Royal York Toronto": [
        "Fairmont Royal York Toronto"
    ],
    "The Ritz-Carlton Toronto": [
        "The Ritz-Carlton Toronto"
    ],
    "1 Hotel Toronto": [
        "1 Hotel Toronto"
    ]
}
SLUGS = ["four-seasons-hotel-toronto-toronto", "fairmont-royal-york-toronto-toronto", "the-ritz-carlton-toronto-toronto", "1-hotel-toronto-toronto"]


def main():
    a = parse_args()
    j = Judge('Booking--39', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_toronto_pet_parking",
            (search_url_with(t, ["toronto", "pet_friendly=1"]) and search_url_with(t, ["parking=1"]))
            or any(visited_property(t, s) for s in SLUGS),
            "Toronto results with the pet-friendly/parking filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")
    j.check("answer_mentions_pet_and_parking",
            contains_any(fa, ["pet"]) and contains_any(fa, ["parking"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
