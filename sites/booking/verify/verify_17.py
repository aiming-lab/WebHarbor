#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--17.

Find a Paris hotel with a fitness center and rating 8+ for 5 nights from
February 14, 2024, sorted by best reviewed.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris properties with a fitness center and rating >= 8.0 (10
    qualify; sorting by review score puts the 9.6-rated property first).

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
    "Too Hotel &amp; Spa Paris - MGallery Collection": [
        "Too Hotel & Spa Paris - MGallery Collection",
        "Too Hotel and Spa Paris - MGallery Collection"
    ],
    "Hôtel Le Milie Rose": [
        "Hotel Le Milie Rose",
        "Hôtel Le Milie Rose"
    ],
    "Paris j'Adore Hotel &amp; Spa": [
        "Paris j'Adore Hotel & Spa",
        "Paris j'Adore Hotel and Spa"
    ],
    "Quinzerie hôtel": [
        "Quinzerie hotel",
        "Quinzerie hôtel"
    ],
    "Le Bristol Paris": [
        "Le Bristol Paris"
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
    ],
    "Hotel Le Louvre Paris": [
        "Hotel Le Louvre Paris"
    ],
    "Melia Paris Louvre": [
        "Melia Paris Louvre"
    ]
}
SLUGS = ["too-hotel-amp-spa-paris-mgallery-collection-paris", "hôtel-le-milie-rose-paris", "paris-jadore-hotel-amp-spa-paris", "quinzerie-hôtel-paris", "le-bristol-paris-paris", "hôtel-de-crillon-paris", "hotel-fabric-paris", "le-marais-suites-paris", "hotel-le-louvre-paris-paris", "melia-paris-louvre-paris"]


def main():
    a = parse_args()
    j = Judge('Booking--17', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paris_best_reviewed_sort",
            (search_url_with(t, ["paris"])
             and (search_url_with(t, ["sort=review_score_desc"]) or search_url_with(t, ["sort=best_reviewed"])
                  or search_url_with(t, ["sort=review_score"]) or search_url_with(t, ["sort=rating"])))
            or any(visited_property(t, s) for s in SLUGS),
            "Paris results with the best-reviewed sort applied (the task demands the sort;"
            " the gym/8+ set is enforced by the answer check), or qualifying property pages")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} Paris gym 8+ properties")
    j.emit()


if __name__ == "__main__":
    main()
