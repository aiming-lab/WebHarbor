#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--18.

Search a London hotel with user rating 8+ for Feb 14-21 2024 for a couple;
provide the name and a short description.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    London properties rated >= 8.0 (6 qualify).

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
    "art'otel London Hoxton": [
        "art'otel London Hoxton"
    ],
    "room2 London Chiswick Hometel": [
        "room2 London Chiswick Hometel"
    ],
    "Page8, Page Hotels": [
        "Page8, Page Hotels"
    ],
    "Vintry &amp; Mercer Hotel - Small Luxury Hotels of the World": [
        "Vintry & Mercer Hotel - Small Luxury Hotels of the World",
        "Vintry and Mercer Hotel - Small Luxury Hotels of the World"
    ],
    "The Savoy": [
        "The Savoy"
    ],
    "Claridge's": [
        "Claridge's"
    ]
}
SLUGS = ["artotel-london-hoxton-london", "room2-london-chiswick-hometel-london", "page8-page-hotels-london", "vintry-amp-mercer-hotel-small-luxury-hotels-of-the-world-london", "the-savoy-london", "claridges-london"]


def main():
    a = parse_args()
    j = Judge('Booking--18', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_london_8plus",
            search_url_with(t, ["london"])
            or any(visited_property(t, s) for s in SLUGS),
            "the London results page (cards show ratings and short descriptions) or a"
            " qualifying property page; the 8+ set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} London 8+ properties")
    j.check("answer_has_description", len(norm(fa).split()) >= 15,
            f"final={fa[:300]!r} answer must describe the hotel, not just name it")
    j.emit()


if __name__ == "__main__":
    main()
