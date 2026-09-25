#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--2.

Task: Compare the prices and chips for the iPhone 14 Pro and iPhone 15 Pro models directly from Apple's website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/iphone-14-pro: $999.00, A16 Bionic (release date September 16, 2022).
    /product/iphone-15-pro: $999.00, A17 Pro (release date September 22, 2023).
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
    j = Judge('Apple--2', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_paths_all(t, ["/product/iphone-14-pro", "/product/iphone-15-pro"])
    j.check("nav_both_product_pages", nav,
            "expected both /product/iphone-14-pro and /product/iphone-15-pro")
    j.check("answer_price_999", price_in(fa, 999), f"final={fa[:200]!r}")
    j.check("answer_chips_a16_a17", contains_all(fa, ["a16", "a17"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
