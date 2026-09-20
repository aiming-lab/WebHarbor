#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--26.

Find a 3-star-or-higher Paris hotel with guest rating above 8.0 and parking,
for February 20-23 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Paris properties with stars >= 3, rating >= 8.0 and parking (8 qualify).

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
    "Drawing House": [
        "Drawing House"
    ],
    "La Demeure Montaigne": [
        "La Demeure Montaigne"
    ],
    "Hôtel La Canopée": [
        "Hotel La Canopee",
        "Hôtel La Canopée"
    ],
    "Hôtel de Crillon": [
        "Hotel de Crillon",
        "Hôtel de Crillon"
    ],
    "Hotel Fabric": [
        "Hotel Fabric"
    ],
    "Le Marais Suites": [
        "Le Marais Suites"
    ]
}
SLUGS = ["175-paris-le-charme-paris", "too-hotel-amp-spa-paris-mgallery-collection-paris", "drawing-house-paris", "la-demeure-montaigne-paris", "hôtel-la-canopée-paris", "hôtel-de-crillon-paris", "hotel-fabric-paris", "le-marais-suites-paris"]


def main():
    a = parse_args()
    j = Judge('Booking--26', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paris_3star_8_parking",
            (search_url_with(t, ["paris", "min_stars=3"]) and search_url_with(t, ["min_rating=8"])
             and search_url_with(t, ["parking=1"]))
            or any(visited_property(t, s) for s in SLUGS),
            "Paris results with the 3-star/8+/parking filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
