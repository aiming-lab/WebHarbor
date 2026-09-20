#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--14.

Book a highly-rated hotel with a swimming pool and free WiFi near the
Louvre in Paris for the weekend of March 3-5, 2024 (login + book).

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris pool+WiFi properties near the Louvre (Louvre landmark tag or within
    1.5 miles of the Louvre) with a high rating: Drawing House, Hotel Le Louvre Paris, Melia Paris Louvre.
    The reservation must carry the March 3-5 dates.

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
    "Drawing House": [
        "Drawing House"
    ],
    "Hotel Le Louvre Paris": [
        "Hotel Le Louvre Paris"
    ],
    "Melia Paris Louvre": [
        "Melia Paris Louvre"
    ]
}
PROPERTY_IDS = [162, 274, 275]
SLUGS = ["drawing-house-paris", "hotel-le-louvre-paris-paris", "melia-paris-louvre-paris"]
DATES_MD = ("03-03", "03-05")


def main():
    a = parse_args()
    j = Judge('Booking--14', a.no_llm)
    t, fa = grade_booking(j, a, PROPERTY_IDS, expect_md=DATES_MD)
    j.check("nav_louvre_search",
            search_url_with(t, ["louvre"]) or any(visited_property(t, s) for s in SLUGS),
            "the Louvre results page (cards show the miles-from-Louvre line, pool and WiFi"
            " flags) or a qualifying property page; the pool/WiFi/near-Louvre set is enforced"
            " by the answer + DB checks")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_booked_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {list(ALLOWED)}")
    j.check("answer_pool_wifi_booking",
            contains_any(fa, ["booked", "booking", "reserved", "reservation", "bag", "cart", "confirmed", "reserve"]),
            f"final={fa[:300]!r} pool/WiFi are enforced by the DB check (the allowed set"
            " consists of pool+wifi properties); the answer needs the booking confirmation")
    j.emit()


if __name__ == "__main__":
    main()
