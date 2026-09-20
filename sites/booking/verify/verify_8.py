#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--8.

Get the hotel with the highest review score and free cancellation in
Chennai, Dec 20-21 2023.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Chennai properties with free cancellation: Park Hyatt Chennai (9.6),
    The Raintree Hotel Chennai (9.4), ITC Grand Chola Chennai (8.3).
    Highest review score: Park Hyatt Chennai at 9.6.

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

HOTEL = "Park Hyatt Chennai"
SLUG = "park-hyatt-chennai-chennai"


def main():
    a = parse_args()
    j = Judge('Booking--8', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_chennai_search_or_prop",
            search_url_with(t, ["chennai"]) or visited_property(t, SLUG),
            "the Chennai results page (cards show ratings and the free-cancellation flag)"
            " or the qualifying property page")
    j.check("answer_highest_scored", contains_any(fa, ["park hyatt"]),
            f"final={fa[:200]!r} expected {HOTEL!r}")
    j.check("answer_score", contains_any(fa, ["9.6", "8.9"]),
            f"final={fa[:200]!r} the results card shows 9.6; the property page's guest-review widget shows 8.9")
    j.emit()


if __name__ == "__main__":
    main()
