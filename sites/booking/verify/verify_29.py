#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--29.

Search for a Toronto hotel with a fitness center and rating 8+, two nights
March 5-7 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Toronto properties with a fitness center and rating >= 8.0 (6 qualify).

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
    "The Ritz-Carlton Toronto": [
        "The Ritz-Carlton Toronto"
    ],
    "Chelsea Hotel Toronto": [
        "Chelsea Hotel Toronto"
    ],
    "Hotel X Toronto": [
        "Hotel X Toronto"
    ],
    "1 Hotel Toronto": [
        "1 Hotel Toronto"
    ],
    "Delta Hotels Toronto": [
        "Delta Hotels Toronto"
    ]
}
SLUGS = ["four-seasons-hotel-toronto-toronto", "the-ritz-carlton-toronto-toronto", "chelsea-hotel-toronto-toronto", "hotel-x-toronto-toronto", "1-hotel-toronto-toronto", "delta-hotels-toronto-toronto"]


def main():
    a = parse_args()
    j = Judge('Booking--29', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_toronto_gym_8",
            search_url_with(t, ["toronto"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Toronto results page (cards show ratings and the fitness-center flag) or a qualifying property page; the gym/8+ set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
