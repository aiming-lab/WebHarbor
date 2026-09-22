#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--30.

Task: Check the storage options and prices for the latest iPad Pro models on Apple's website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    The current iPad Pro pages list storage 256GB (base), 512GB +$200, 1TB
    +$400, 2TB +$530; iPad Pro M5 / 11-inch M4 From $999.00, 13-inch M4
    From $1299.00.
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
    j = Judge('Apple--30', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/ipad-pro-m5", "/product/ipad-pro-11-inch-m4",
                             "/product/ipad-pro-13-inch-m4"])
           or navigated_path(t, "/ipad"))
    j.check("nav_latest_ipad_pro", nav, "expected an iPad Pro page or /ipad")
    j.check("answer_storage_options",
            contains_all(fa, ["256gb", "512gb", "1tb", "2tb"]), f"final={fa[:200]!r}")
    j.check("answer_prices",
            price_in(fa, 999) or (price_in(fa, 200) and price_in(fa, 400)),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
