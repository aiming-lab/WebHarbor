#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--28.

Find a Dubai hotel with a swimming pool for a week-long stay Feb 22-29 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Dubai properties with a swimming pool (5 qualify).

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
    "Palace Dubai Creek Harbour": [
        "Palace Dubai Creek Harbour"
    ],
    "The Lana - Dorchester Collection": [
        "The Lana - Dorchester Collection"
    ],
    "Vida Dubai Marina &amp; Yacht Club": [
        "Vida Dubai Marina & Yacht Club",
        "Vida Dubai Marina and Yacht Club"
    ],
    "Burj Al Arab Jumeirah": [
        "Burj Al Arab Jumeirah"
    ],
    "Atlantis The Palm": [
        "Atlantis The Palm"
    ]
}
SLUGS = ["palace-dubai-creek-harbour-dubai", "the-lana-dorchester-collection-dubai", "vida-dubai-marina-amp-yacht-club-dubai", "burj-al-arab-jumeirah-dubai", "atlantis-the-palm-dubai"]


def main():
    a = parse_args()
    j = Judge('Booking--28', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_dubai_pool",
            search_url_with(t, ["dubai"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Dubai results page (cards show the pool flag) or a qualifying property page; the pool set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")
    j.check("answer_mentions_pool", contains_affirmative(fa, ["pool"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
