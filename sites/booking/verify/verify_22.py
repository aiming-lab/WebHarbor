#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--22.

Search for an Amsterdam hotel with review score 9+ and bicycle rentals for a
week-long stay March 15-22 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Amsterdam properties with rating >= 9.0 and bicycle rental (3): Hotel 717,
    Tribe Amsterdam City, Mercure Amsterdam North Station.

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
    "Hotel 717": [
        "Hotel 717"
    ],
    "Tribe Amsterdam City": [
        "Tribe Amsterdam City"
    ],
    "Mercure Amsterdam North Station": [
        "Mercure Amsterdam North Station"
    ]
}
SLUGS = ["hotel-717-amsterdam", "tribe-amsterdam-city-amsterdam", "mercure-amsterdam-north-station-amsterdam"]


def main():
    a = parse_args()
    j = Judge('Booking--22', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_amsterdam_9_bicycle",
            search_url_with(t, ["amsterdam"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Amsterdam results page (cards show ratings and the bicycle-rental flag) or a qualifying property page; the 9+/bicycle set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")
    j.check("answer_mentions_bicycle", contains_any(fa, ["bicycle", "bike"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
