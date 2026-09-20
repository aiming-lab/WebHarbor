#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--6.

Book one room which provides breakfast and airport shuttle from Jan 22 to 25
in Los Angeles (login + reserve; the login page publishes the demo account).

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Los Angeles properties with breakfast included AND airport shuttle:
    Luskin Hotel, The Garland, The Prospect Hollywood. The reservation must carry the Jan 22-25 dates.

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
    "Luskin Hotel": [
        "Luskin Hotel"
    ],
    "The Garland": [
        "The Garland"
    ],
    "The Prospect Hollywood": [
        "The Prospect Hollywood"
    ]
}
PROPERTY_IDS = [109, 111, 114]
SLUGS = ["luskin-hotel-los-angeles", "the-garland-los-angeles", "the-prospect-hollywood-los-angeles"]
DATES_MD = ("01-22", "01-25")


def main():
    a = parse_args()
    j = Judge('Booking--6', a.no_llm)
    t, fa = grade_booking(j, a, PROPERTY_IDS, expect_md=DATES_MD)
    j.check("nav_la_search",
            search_url_with(t, ["los angeles"]) or any(visited_property(t, s) for s in SLUGS),
            "the LA results page or a qualifying property page (the booked property set"
            " and dates are enforced by the DB state check)")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_booked_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {list(ALLOWED)}")
    j.check("answer_confirms_booking",
            contains_any(fa, ["booked", "booking", "reserved", "reservation", "bag", "cart", "confirmed", "reserve"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
