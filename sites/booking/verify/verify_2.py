#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--2.

Find a hotel in Ohio for December 20-23 for 3 adults and 2 rooms.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Ohio properties able to host >=3 guests (10 qualify; e.g.
    Hilton Columbus Downtown, Comfort Inn Ohio, Holiday Inn Express Dayton).
    One Ohio property (max 2 guests) cannot host 3 adults.
    Navigation pins the pseudo-city query q=ohio (or /city/ohio): the mirror
    models Ohio as a single city, so a city-level query (e.g. Columbus) is not
    an accepted navigation for this task.

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
    "The Ritz-Carlton Cleveland": [
        "The Ritz-Carlton Cleveland"
    ],
    "Hilton Columbus Downtown": [
        "Hilton Columbus Downtown"
    ],
    "Hotel Brexton Cincinnati": [
        "Hotel Brexton Cincinnati"
    ],
    "Comfort Inn Ohio": [
        "Comfort Inn Ohio"
    ],
    "Holiday Inn Express Dayton": [
        "Holiday Inn Express Dayton"
    ],
    "Kinley Cincinnati Downtown": [
        "Kinley Cincinnati Downtown"
    ],
    "The Westin Cleveland Downtown": [
        "The Westin Cleveland Downtown"
    ],
    "Graduate Columbus": [
        "Graduate Columbus"
    ],
    "Renaissance Columbus Downtown": [
        "Renaissance Columbus Downtown"
    ],
    "Residence Inn Akron Fairlawn": [
        "Residence Inn Akron Fairlawn"
    ]
}


def main():
    a = parse_args()
    j = Judge('Booking--2', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_ohio_search", search_url_with(t, ["q=ohio"]) or navigated_to(t, "/city/ohio"),
            "an Ohio results page (the adults=3 occupancy filter narrows to >=3-guest properties)")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_ohio_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} Ohio properties that host 3+ guests")
    j.emit()


if __name__ == "__main__":
    main()
