#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--15.

Find the highest-rated luxury hotel in Rome for Jan 10-20 2024 (2 adults);
include cost, amenities, customer rating.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    5-star (luxury) Rome hotels: Hotel de Russie (8.6, $304.2/night
    effective, $338.0 list), Hotel Eden (8.0), Casa Trastevere (8.0).
    Highest-rated: Hotel de Russie. Amenities include: Tea/coffee maker, Family rooms, Beachfront, Kitchen, Pet-friendly, Garden view, Free parking, Breakfast included.

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

HOTEL = "Hotel de Russie"
SLUG = "hotel-de-russie-rome"
PRICE_SET = [304, 304.2, 338, 3040, 3042]
RATING_SET = ["8.6", "9.1"]
AMENITIES = ["Tea/coffee maker", "Family rooms", "Beachfront", "Kitchen", "Pet-friendly", "Garden view", "Free parking", "Breakfast included", "Swimming pool", "Spa & wellness", "Fitness center", "Restaurant"]


def main():
    a = parse_args()
    j = Judge('Booking--15', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_rome_luxury",
            search_url_with(t, ["rome"]) or visited_property(t, SLUG) or navigated_to(t, "category/luxury"),
            "the Rome results page (cards show star ratings and amenity flags) or the property page")
    j.check("answer_highest_rated_hotel", contains_any(fa, ["de russie"]),
            f"final={fa[:200]!r} expected {HOTEL!r}")
    j.check("answer_cost", any(price_in(fa, p) for p in PRICE_SET),
            f"final={fa[:200]!r} accepted={PRICE_SET}")
    j.check("answer_rating", any(x in fa for x in RATING_SET),
            f"final={fa[:200]!r} the results card shows 8.6; the property page's guest-review widget shows 9.1")
    amen_hits = [x for x in AMENITIES if norm(x) in norm(fa)]
    j.check("answer_amenities", len(amen_hits) >= 2,
            f"final={fa[:300]!r} amenities mentioned={amen_hits}")
    j.emit()


if __name__ == "__main__":
    main()
