#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--7.

Find a hotel room on January 3-6 closest to the National University of
Singapore that costs less than $500.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The landmark search for the National University of Singapore sorts result
    cards by distance ("X.X miles from National University of Singapore").
    Closest: The Fullerton Hotel Singapore at 2.4 miles, $349/night (well
    under $500); every other Singapore property is farther (next: 3.0 miles).

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

HOTEL = "The Fullerton Hotel Singapore"
SLUG = "the-fullerton-hotel-singapore-singapore"


def main():
    a = parse_args()
    j = Judge('Booking--7', a.no_llm)
    t, fa = grade_common(j, a)
    import re as _re
    nus_search = any("/search" in u.lower() and ("national+university" in u.lower()
                     or _re.search(r"q=nus(&|$)", u.lower())) for u in step_urls(t))
    j.check("nav_nus_landmark_search", nus_search or visited_property(t, SLUG),
            "the NUS landmark search (cards carry the miles-from-NUS line), or the property page")
    j.check("answer_closest_hotel", contains_any(fa, ["fullerton"]),
            f"final={fa[:200]!r} expected {HOTEL!r}")
    j.check("answer_distance_or_price",
            contains_any(fa, ["2.4", "349"]) or (contains_any(fa, ["miles"]) and contains_any(fa, ["closest", "nearest", "closest to"])),
            f"final={fa[:200]!r} expected the 2.4-mile distance and/or the $349 price")
    j.emit()


if __name__ == "__main__":
    main()
