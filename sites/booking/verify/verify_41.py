#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--41.

Browse Booking's homepage to find out which company it belongs to.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The homepage footer links to About Booking.com; the About page states the
    company is part of Booking Holdings Inc. (NASDAQ: BKNG).

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



def main():
    a = parse_args()
    j = Judge('Booking--41', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_about_page", navigated_to(t, "/about"),
            "the About page (the company fact lives there; the homepage footer links to it)")
    j.check("answer_parent_company", contains_any(fa, ["booking holdings"]),
            f"final={fa[:200]!r} expected the parent company named on the About page")
    j.emit()


if __name__ == "__main__":
    main()
