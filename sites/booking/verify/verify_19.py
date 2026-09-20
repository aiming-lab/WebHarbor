#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--19.

Look for Paris hotels with customer ratings above 8.0 for a weekend stay
March 18-20 2024; list the top three suggestions based on user reviews.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Paris properties rated above 8.0, ranked by review score (ties broken by
    review count): 1. Too Hotel & Spa Paris - MGallery Collection (9.6),
    2. Le Marais Suites (9.4), 3. Quinzerie hotel (9.3). The 4th is 9.1 — the
    top three are unambiguous.

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
    "Too Hotel &amp; Spa Paris - MGallery Collection": [
        "Too Hotel & Spa Paris - MGallery Collection",
        "Too Hotel and Spa Paris - MGallery Collection"
    ],
    "Le Marais Suites": [
        "Le Marais Suites"
    ],
    "Quinzerie hôtel": [
        "Quinzerie hotel",
        "Quinzerie hôtel"
    ]
}
SLUGS = ["too-hotel-amp-spa-paris-mgallery-collection-paris", "le-marais-suites-paris", "quinzerie-hôtel-paris"]


def main():
    a = parse_args()
    j = Judge('Booking--19', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_paris_ranked",
            search_url_with(t, ["paris"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Paris results page (cards show review scores; the above-8.0 set is"
            " enforced by the answer check) or the qualifying property pages")
    missing = [nm for nm in ALLOWED if not any(al.lower() in norm(fa) for al in ALLOWED[nm])]
    j.check("answer_lists_top_three", not missing,
            f"final={fa[:300]!r} missing={missing} expected all of {list(ALLOWED)}")
    j.emit()


if __name__ == "__main__":
    main()
