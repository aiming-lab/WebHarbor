#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--37.

Search for a resort (not a hotel) in Bali for March 20-25 2024; detail the
available dates and any provided tour or cultural experiences.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Bali Resort-type properties (7): Four Seasons Sayan, The Mulia Nusa Dua, COMO Uma Ubud, The Udaya Resort Ubud, Hanging Gardens of Bali, AYANA Resort Bali, Padma Resort Legian.
    Their pages list the property's amenities (spa & wellness, restaurant, beach
    access, airport shuttle, ...) under 'Most popular facilities'.

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
    "Four Seasons Sayan": [
        "Four Seasons Sayan"
    ],
    "The Mulia Nusa Dua": [
        "The Mulia Nusa Dua"
    ],
    "COMO Uma Ubud": [
        "COMO Uma Ubud"
    ],
    "The Udaya Resort Ubud": [
        "The Udaya Resort Ubud"
    ],
    "Hanging Gardens of Bali": [
        "Hanging Gardens of Bali"
    ],
    "AYANA Resort Bali": [
        "AYANA Resort Bali"
    ],
    "Padma Resort Legian": [
        "Padma Resort Legian"
    ]
}
SLUGS = ["four-seasons-sayan-bali", "the-mulia-nusa-dua-bali", "como-uma-ubud-bali", "the-udaya-resort-ubud-bali", "hanging-gardens-of-bali", "ayana-resort-bali", "padma-resort-legian"]
AMENITIES = {
    "Four Seasons Sayan": [
        "Airport shuttle",
        "Washing machine",
        "Balcony",
        "Free WiFi",
        "Bar",
        "Kitchen",
        "24-hour front desk",
        "Garden view",
        "Beachfront",
        "Free parking",
        "Swimming pool",
        "Spa & wellness",
        "Fitness center",
        "Restaurant"
    ],
    "The Mulia Nusa Dua": [
        "Sea view",
        "Balcony",
        "Airport shuttle",
        "Breakfast included",
        "Hair dryer",
        "Non-smoking rooms",
        "Room service",
        "Garden view",
        "Free WiFi",
        "Air conditioning",
        "Pet-friendly",
        "Tea/coffee maker",
        "Swimming pool",
        "Spa & wellness",
        "Fitness center",
        "Restaurant"
    ],
    "COMO Uma Ubud": [
        "BBQ facilities",
        "Room service",
        "Free WiFi",
        "Airport shuttle",
        "Restaurant",
        "Tea/coffee maker",
        "Garden view",
        "Fitness center",
        "24-hour front desk",
        "Beachfront",
        "Free parking",
        "Swimming pool",
        "Spa & wellness"
    ],
    "The Udaya Resort Ubud": [
        "Washing machine",
        "Fitness center",
        "Restaurant",
        "Kitchen",
        "Beachfront",
        "Pet-friendly",
        "Airport shuttle",
        "Balcony",
        "Family rooms",
        "Spa & wellness",
        "Bar",
        "Swimming pool"
    ],
    "Hanging Gardens of Bali": [
        "Wi-Fi",
        "Swimming Pool",
        "Spa & Wellness",
        "Fitness Center",
        "Restaurant",
        "Breakfast",
        "Air Conditioning"
    ],
    "AYANA Resort Bali": [
        "Wi-Fi",
        "Swimming Pool",
        "Spa & Wellness",
        "Fitness Center",
        "Restaurant",
        "Beach Access",
        "Breakfast",
        "Air Conditioning"
    ],
    "Padma Resort Legian": [
        "Wi-Fi",
        "Swimming Pool",
        "Spa & Wellness",
        "Fitness Center",
        "Restaurant",
        "Beach Access",
        "Breakfast",
        "Air Conditioning"
    ]
}


def main():
    a = parse_args()
    j = Judge('Booking--37', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_bali_or_resorts_plus_prop",
            (search_url_with(t, ["bali"]) or navigated_to(t, "/property-type/resorts"))
            and any(visited_property(t, s) for s in SLUGS),
            "a Bali (or property-type resorts) listing plus the resort's own page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_bali_resort", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} Bali resorts")
    if not named:
        j.emit()
    amen_hits = [x for x in AMENITIES[named] if norm(x) in norm(fa)]
    j.check("answer_mentions_amenities", len(amen_hits) >= 2,
            f"final={fa[:300]!r} amenities mentioned={amen_hits}")
    j.check("answer_addresses_dates",
            contains_any(fa, ["march", "2024-03", "mar 20", "03-20", "mar 25", "03-25", "available", "availability"]),
            f"final={fa[:300]!r}")
    j.emit()


if __name__ == "__main__":
    main()
