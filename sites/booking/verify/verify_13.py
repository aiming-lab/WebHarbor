#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--13.

Find and book a Paris hotel for a family of four (2 adults + 2 children)
with free cancellation, Feb 14-21 2024 (login + book).

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris properties that can host a family of four (max_guests >= 4) with
    free cancellation (10 qualify). The reservation must carry the
    February 14-21 dates.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + booking DB delta (cart/booking row for an allowed property with the task dates; everything else unchanged).
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
PROPERTY_IDS = [158, 159, 162, 164, 165, 167, 182, 183, 184, 185]
SLUGS = ["175-paris-le-charme-paris", "les-rives-oceanik-paris", "drawing-house-paris", "hôtel-la-canopée-paris", "hôtel-le-milie-rose-paris", "quinzerie-hôtel-paris", "le-bristol-paris-paris", "hôtel-de-crillon-paris", "hotel-fabric-paris", "le-marais-suites-paris"]
DATES_MD = ("02-14", "02-21")


def main():
    a = parse_args()
    j = Judge('Booking--13', a.no_llm)
    t, fa = grade_booking(j, a, PROPERTY_IDS, expect_md=DATES_MD)
    j.check("nav_paris_search",
            search_url_with(t, ["paris"]) or any(visited_property(t, s) for s in SLUGS),
            "the Paris results page or a qualifying property page (the family-capable "
            "free-cancellation set and dates are enforced by the answer + DB checks)")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_booked_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} family-capable free-cancellation Paris properties")
    j.check("answer_confirms_booking",
            contains_any(fa, ["booked", "booking", "reserved", "reservation", "bag", "cart", "confirmed", "reserve"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
