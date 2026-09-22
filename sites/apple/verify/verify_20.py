#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--20.

Task: Check the price for an Apple iPhone 14 Plus with 256GB storage in Purple color.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/iphone-14-plus: From $899.00; storage 128GB (base), 256GB +$90,
    512GB +$270; Purple is one of the six color options (color does not
    change the price). Selecting 256GB recomputes the page price to
    $989.00 — so the honest answer is $989, or $899 + the $90 storage
    upgrade.
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
    j = Judge('Apple--20', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/product/iphone-14-plus")
           or navigated_path(t, "/configure/iphone-14-plus"))
    j.check("nav_iphone14_plus_page", nav,
            "expected /product/iphone-14-plus or its configurator")
    j.check("answer_price_989_or_899_plus_90",
            price_in(fa, 989) or (price_in(fa, 899) and contains_word(fa, "90")),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
