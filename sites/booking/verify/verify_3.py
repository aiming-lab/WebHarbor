#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--3.

Find a hotel with 4-star-and-above rating in Los Angeles for 3 days from Dec 18.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Los Angeles properties with >=4 stars (8 qualify).

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
    "H by H Hospitality": [
        "H by H Hospitality"
    ],
    "The Garland": [
        "The Garland"
    ],
    "Conrad Los Angeles": [
        "Conrad Los Angeles"
    ],
    "The Prospect Hollywood": [
        "The Prospect Hollywood"
    ],
    "Le Petit Pali Brentwood": [
        "Le Petit Pali Brentwood"
    ],
    "Waldorf Astoria Beverly Hills": [
        "Waldorf Astoria Beverly Hills"
    ],
    "Hilton LAX": [
        "Hilton LAX"
    ],
    "Marriott LAX Airport": [
        "Marriott LAX Airport"
    ]
}
SLUGS = ["h-by-h-hospitality-los-angeles", "the-garland-los-angeles", "conrad-los-angeles-los-angeles", "the-prospect-hollywood-los-angeles", "le-petit-pali-brentwood-los-angeles", "waldorf-astoria-beverly-hills-los-angeles", "hilton-lax-los-angeles", "marriott-lax-airport-los-angeles"]


def main():
    a = parse_args()
    j = Judge('Booking--3', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_la_search_or_prop",
            search_url_with(t, ["los angeles"]) or navigated_to(t, "stars=4")
            or any(visited_property(t, s) for s in SLUGS),
            "the LA results page (star ratings render on every card) or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_4star_la_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} 4+ star LA properties")
    j.emit()


if __name__ == "__main__":
    main()
