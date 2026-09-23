#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--30.

Search London hotels March 20-23 2024; how many hotels are left after
applying the Breakfast included and Fitness center filters?

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Applying both filters together leaves exactly 3 London properties
    (the results page shows '3 properties found').

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

COUNT = 3


def main():
    a = parse_args()
    j = Judge('Booking--30', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_london_bkf_gym_filters",
            (search_url_with(t, ["london", "breakfast=1"]) and search_url_with(t, ["gym=1"])),
            "London results with the breakfast AND fitness filters applied together")
    import re as _re
    f = norm(fa)
    only_three = _re.findall(r"(?<![\d.])\d+(?![\d.])", f) == ["3"]
    j.check("answer_count", count_claim(fa, COUNT) or only_three,
            f"final={fa[:200]!r} expected the count {COUNT}")
    j.emit()


if __name__ == "__main__":
    main()
