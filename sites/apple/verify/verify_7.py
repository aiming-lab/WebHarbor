#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--7.

Task: When and where the Apple Vision Pro will be released.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /vision-pro and /product/apple-vision-pro state: Released February 2,
    2024 in the United States ("Release date: February 2, 2024 (United
    States)", "Available in: United States").
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, step_urls, url_query, navigated_to,
                        navigated_any, navigated_path, navigated_paths_all,
                        visited_url_with, contains_all, contains_any,
                        contains_word, contains_words_any, price_in,
                        count_named, number_claim, is_jan10_2024, Judge,
                        parse_args)


def main():
    a = parse_args()
    j = Judge('Apple--7', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/vision-pro", "/product/apple-vision-pro"])
    j.check("nav_vision_pro", nav, "expected /vision-pro or /product/apple-vision-pro")
    j.check("answer_date_feb_2_2024",
            (contains_all(fa, ["february"]) and (contains_word(fa, "2") or contains_word(fa, "02"))
             and contains_all(fa, ["2024"]))
            or contains_any(fa, ["2024-02-02", "02/02/2024"]),
            f"final={fa[:200]!r}")
    j.check("answer_place_united_states",
            contains_any(fa, ["united states", "america", "u.s.", "usa"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
