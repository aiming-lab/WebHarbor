#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--32.

Look for Sydney hotels Feb 24-27 2024; after the Swimming Pool and Airport
Shuttle filters, what is the total number of hotels available?

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Applying both filters together leaves exactly 3 Sydney properties
    (the results page shows '3 properties found').

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

COUNT = 3


def main():
    a = parse_args()
    j = Judge('Booking--32', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_sydney_pool_shuttle_filters",
            (search_url_with(t, ["sydney", "pool=1"]) and search_url_with(t, ["airport_shuttle=1"])),
            "Sydney results with the pool AND airport-shuttle filters applied together")
    import re as _re
    f = norm(fa)
    only_three = _re.findall(r"(?<![\d.])\d+(?![\d.])", f) == ["3"]
    j.check("answer_count", count_claim(fa, COUNT) or only_three,
            f"final={fa[:200]!r} expected the count {COUNT}")
    j.emit()


if __name__ == "__main__":
    main()
