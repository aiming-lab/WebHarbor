#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--37.

Task: Compare the color options of iPhone 13 Pro, iPhone 14 Pro and iPhone 15 Pro.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/iphone-13-pro: Graphite, Gold, Silver, Sierra Blue, Alpine
    Green. /product/iphone-14-pro: Deep Purple, Gold, Silver, Space Black.
    /product/iphone-15-pro: Natural Titanium, Blue Titanium, White
    Titanium, Black Titanium.
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
    j = Judge('Apple--37', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_paths_all(t, ["/product/iphone-13-pro", "/product/iphone-14-pro",
                                  "/product/iphone-15-pro"])
    j.check("nav_all_three_pages", nav,
            "expected all three product pages /product/iphone-13-pro, "
            "/product/iphone-14-pro, /product/iphone-15-pro")
    c13 = contains_any(fa, ["sierra blue", "alpine green", "graphite"])
    c14 = contains_any(fa, ["deep purple", "space black"])
    c15 = contains_any(fa, ["natural titanium", "blue titanium", "black titanium",
                            "white titanium"])
    j.check("answer_13pro_color", c13, f"final={fa[:200]!r}")
    j.check("answer_14pro_color", c14, f"final={fa[:200]!r}")
    j.check("answer_15pro_color", c15, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
