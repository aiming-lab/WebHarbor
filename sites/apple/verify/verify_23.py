#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--23.

Task: Determine the price difference between the latest series of Apple Watch and Apple Watch SE on the Apple website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /watch: Apple Watch Series 11 From $399.00; Apple Watch SE From $249.00
    — a $150 difference.
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
    j = Judge('Apple--23', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/watch")
           or navigated_paths_all(t, ["/product/apple-watch-series-11",
                                      "/product/apple-watch-se"]))
    j.check("nav_watch_pages", nav,
            "expected /watch or both watch product pages")
    j.check("answer_prices",
            price_in(fa, 399) and price_in(fa, 249), f"final={fa[:200]!r}")
    j.check("answer_difference_150", price_in(fa, 150), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
