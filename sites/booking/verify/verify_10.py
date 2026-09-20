#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--10.

Find a well-reviewed hotel in Paris for a couple, Feb 14-21 2024, offering
free cancellation.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris properties with free cancellation (10; all are
    well-reviewed, rating >= 8.0 on the mirror).

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
    "Les Rives Oceanik": [
        "Les Rives Oceanik"
    ],
    "Drawing House": [
        "Drawing House"
    ],
    "Hôtel La Canopée": [
        "Hotel La Canopee",
        "Hôtel La Canopée"
    ],
    "Hôtel Le Milie Rose": [
        "Hotel Le Milie Rose",
        "Hôtel Le Milie Rose"
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
    ]
}
SLUGS = ["175-paris-le-charme-paris", "les-rives-oceanik-paris", "drawing-house-paris", "hôtel-la-canopée-paris", "hôtel-le-milie-rose-paris", "quinzerie-hôtel-paris", "le-bristol-paris-paris", "hôtel-de-crillon-paris", "hotel-fabric-paris", "le-marais-suites-paris"]


def main():
    a = parse_args()
    j = Judge('Booking--10', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paris_free_cancel",
            search_url_with(t, ["paris"]) or any(visited_property(t, s) for s in SLUGS),
            "the Paris results page (cards show the free-cancellation flag) or a"
            " qualifying property page; the free-cancellation set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} free-cancellation Paris properties")
    j.check("answer_mentions_free_cancellation", contains_any(fa, ["free cancellation", "cancellation"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
