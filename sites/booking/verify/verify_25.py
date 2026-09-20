#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--25.

Search for a Lisbon hotel with airport shuttle, rated 8.5+, six nights March
1-7 2024, two adults, breakfast included.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Lisbon properties with rating >= 8.5, airport shuttle and breakfast (7):
    Four Seasons Hotel Ritz Lisbon, Bairro Alto Hotel Lisbon, Pestana Palace Lisbon, Casa das Janelas Lisbon, Altis Grand Hotel Lisbon, Corinthia Lisbon, Tivoli Avenida Liberdade Lisbon.

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
    "Four Seasons Hotel Ritz Lisbon": [
        "Four Seasons Hotel Ritz Lisbon"
    ],
    "Bairro Alto Hotel Lisbon": [
        "Bairro Alto Hotel Lisbon"
    ],
    "Pestana Palace Lisbon": [
        "Pestana Palace Lisbon"
    ],
    "Casa das Janelas Lisbon": [
        "Casa das Janelas Lisbon"
    ],
    "Altis Grand Hotel Lisbon": [
        "Altis Grand Hotel Lisbon"
    ],
    "Corinthia Lisbon": [
        "Corinthia Lisbon"
    ],
    "Tivoli Avenida Liberdade Lisbon": [
        "Tivoli Avenida Liberdade Lisbon"
    ]
}
SLUGS = ["four-seasons-hotel-ritz-lisbon-lisbon", "bairro-alto-hotel-lisbon-lisbon", "pestana-palace-lisbon-lisbon", "casa-das-janelas-lisbon-lisbon", "altis-grand-hotel-lisbon-lisbon", "corinthia-lisbon-lisbon", "tivoli-avenida-liberdade-lisbon-lisbon"]


def main():
    a = parse_args()
    j = Judge('Booking--25', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_lisbon_shuttle_bkf",
            search_url_with(t, ["lisbon"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Lisbon results page (cards show ratings and the shuttle/breakfast flags) or a qualifying property page; the 8.5+/shuttle/breakfast set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
