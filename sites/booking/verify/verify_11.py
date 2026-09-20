#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--11.

Reserve a downtown Chicago hotel with rating 9+, free cancellation and a
fitness center, March 20-27 2024 (login + reserve).

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Chicago properties with rating >= 9.0, free cancellation and a fitness
    center: The Peninsula Chicago, Four Seasons Hotel Chicago, The Langham Chicago, Waldorf Astoria Chicago (the first three are in the Downtown Chicago
    neighborhood). The reservation must carry the March 20-27 dates.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + booking DB delta (cart/booking row for an allowed property with the task dates; everything else unchanged).
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
    "The Peninsula Chicago": [
        "The Peninsula Chicago"
    ],
    "Four Seasons Hotel Chicago": [
        "Four Seasons Hotel Chicago"
    ],
    "The Langham Chicago": [
        "The Langham Chicago"
    ],
    "Waldorf Astoria Chicago": [
        "Waldorf Astoria Chicago"
    ]
}
PROPERTY_IDS = [233, 234, 235, 296]
SLUGS = ["the-peninsula-chicago-chicago", "four-seasons-hotel-chicago-chicago", "the-langham-chicago-chicago", "waldorf-astoria-chicago-chicago"]
DATES_MD = ("03-20", "03-27")


def main():
    a = parse_args()
    j = Judge('Booking--11', a.no_llm)
    t, fa = grade_booking(j, a, PROPERTY_IDS, expect_md=DATES_MD)
    j.check("nav_chicago_search",
            search_url_with(t, ["chicago"]) or any(visited_property(t, s) for s in SLUGS),
            "the Chicago results page or a qualifying property page (the rating/cancellation/"
            "gym set and dates are enforced by the answer + DB checks)")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_booked_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {list(ALLOWED)}")
    j.check("answer_confirms_booking",
            contains_any(fa, ["booked", "booking", "reserved", "reservation", "bag", "cart", "confirmed", "reserve"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
