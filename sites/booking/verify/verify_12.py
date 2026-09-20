#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--12.

Find a hotel in Paris with review score 8+, free WiFi, 5 nights from
January 5, 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris properties with rating >= 8.0 AND free WiFi (8 qualify).

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
    "1.75 Paris Le Charme": [
        "1.75 Paris Le Charme"
    ],
    "Too Hotel &amp; Spa Paris - MGallery Collection": [
        "Too Hotel & Spa Paris - MGallery Collection",
        "Too Hotel and Spa Paris - MGallery Collection"
    ],
    "SO/ Paris Hotel": [
        "SO/ Paris Hotel"
    ],
    "Drawing House": [
        "Drawing House"
    ],
    "La Demeure Montaigne": [
        "La Demeure Montaigne"
    ],
    "Hôtel Le Milie Rose": [
        "Hotel Le Milie Rose",
        "Hôtel Le Milie Rose"
    ],
    "Hotel Le Louvre Paris": [
        "Hotel Le Louvre Paris"
    ],
    "Melia Paris Louvre": [
        "Melia Paris Louvre"
    ]
}
SLUGS = ["175-paris-le-charme-paris", "too-hotel-amp-spa-paris-mgallery-collection-paris", "so-paris-hotel-paris", "drawing-house-paris", "la-demeure-montaigne-paris", "hôtel-le-milie-rose-paris", "hotel-le-louvre-paris-paris", "melia-paris-louvre-paris"]


def main():
    a = parse_args()
    j = Judge('Booking--12', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paris_8plus_wifi",
            search_url_with(t, ["paris"]) or any(visited_property(t, s) for s in SLUGS),
            "the Paris results page (cards show ratings and the WiFi flag) or a"
            " qualifying property page; the 8+/WiFi set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} Paris 8+/WiFi properties")
    j.emit()


if __name__ == "__main__":
    main()
