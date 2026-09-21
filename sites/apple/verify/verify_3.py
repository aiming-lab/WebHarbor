#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--3.

Task: Find the latest model of the iPhone and compare the price and screen size between the pro and pro max.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    The newest iPhone line is the 17 series: /product/iphone-17-pro shows
    $1099.00 with a 6.3" Super Retina XDR display; /product/iphone-17-pro-max
    shows $1199.00 with a 6.9" display.
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
    j = Judge('Apple--3', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_paths_all(t, ["/product/iphone-17-pro", "/product/iphone-17-pro-max"])
    j.check("nav_both_product_pages", nav,
            "expected both /product/iphone-17-pro and /product/iphone-17-pro-max")
    j.check("answer_prices", price_in(fa, 1099) and price_in(fa, 1199), f"final={fa[:200]!r}")
    j.check("answer_screen_sizes", contains_all(fa, ["6.3", "6.9"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
