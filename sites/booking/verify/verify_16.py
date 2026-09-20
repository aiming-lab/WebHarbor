#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--16.

Find a Paris hotel with rating 9+, free WiFi, breakfast included, 5 nights
from January 15, 2024; provide name, location and price per night.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris 9+/WiFi/breakfast properties (3): 1.75 Paris Le Charme ($228.80
    effective, 13th arr.), Too Hotel & Spa Paris - MGallery Collection ($287.00,
    13th arr.), Melia Paris Louvre ($212.25 effective, Louvre).

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
    "1.75 Paris Le Charme": [
        "1.75 Paris Le Charme"
    ],
    "Too Hotel &amp; Spa Paris - MGallery Collection": [
        "Too Hotel & Spa Paris - MGallery Collection",
        "Too Hotel and Spa Paris - MGallery Collection"
    ],
    "Melia Paris Louvre": [
        "Melia Paris Louvre"
    ]
}
SLUGS = ["175-paris-le-charme-paris", "too-hotel-amp-spa-paris-mgallery-collection-paris", "melia-paris-louvre-paris"]
PRICES = {
    "1.75 Paris Le Charme": [
        228.8,
        229,
        286.0,
        286
    ],
    "Too Hotel &amp; Spa Paris - MGallery Collection": [
        287.0,
        287,
        410.0,
        410
    ],
    "Melia Paris Louvre": [
        212.25,
        212,
        283.0,
        283
    ]
}
LOCS = {
    "1.75 Paris Le Charme": [
        "13th arr.",
        "13th",
        "13th arrondissement"
    ],
    "Too Hotel &amp; Spa Paris - MGallery Collection": [
        "13th arr.",
        "13th",
        "13th arrondissement"
    ],
    "Melia Paris Louvre": [
        "Louvre",
        "Louvre - Tuileries"
    ]
}


def main():
    a = parse_args()
    j = Judge('Booking--16', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paris_9_wifi_bkf",
            search_url_with(t, ["paris"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Paris results page (cards show ratings, WiFi and breakfast flags)"
            " or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_hotel", bool(named), f"final={fa[:200]!r} expected one of {list(ALLOWED)}")
    if named:
        j.check("answer_price_per_night", any(price_in(fa, p) for p in PRICES[named]),
                f"final={fa[:200]!r} accepted for {named!r}={PRICES[named]}")
        j.check("answer_location", any(norm(x) in norm(fa) for x in LOCS[named]),
                f"final={fa[:200]!r} expected location {LOCS[named]}")
    else:
        j.check("answer_price_per_night", False, "no named property")
        j.check("answer_location", False, "no named property")
    j.emit()


if __name__ == "__main__":
    main()
