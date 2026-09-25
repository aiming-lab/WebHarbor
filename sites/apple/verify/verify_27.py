#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--27.

Task: On Apple's website, check if the HomePod mini in store is available in multiple colors and list them.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/homepod-mini: "HomePod mini is available in five vibrant
    colors" — White, Yellow, Orange, Blue, Space Gray.
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
    j = Judge('Apple--27', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_path(t, "/product/homepod-mini")
    j.check("nav_homepod_mini_page", nav, "expected /product/homepod-mini")
    colors = ["white", "yellow", "orange", "blue", "space gray"]
    found = sum(1 for c in colors if contains_word(fa, c))
    j.check("answer_four_plus_colors_listed", found >= 4, f"colors matched={found}")
    j.emit()


if __name__ == "__main__":
    main()
