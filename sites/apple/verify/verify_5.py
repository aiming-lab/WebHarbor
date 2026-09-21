#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--5.

Task: Check the release date and price for the latest version of the iPhone.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    The newest iPhones on the mirror are the 17 series; their product pages
    show no Release date row, only "Release year 2024" (iPhone 17 Pro From
    $1099.00, iPhone 17 Pro Max From $1199.00). A report of the release year
    2024, or an explicit statement that no exact date is listed, is the
    honest on-page answer.
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
    j = Judge('Apple--5', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/iphone")
           or navigated_any(t, ["/product/iphone-17-pro", "/product/iphone-17-pro-max",
                                "/product/iphone-17", "/product/iphone-17e",
                                "/product/iphone-air"]))
    j.check("nav_latest_iphone", nav, "expected /iphone or an iPhone 17-series product page")
    j.check("answer_latest_iphone_price",
            price_in(fa, 1099) or price_in(fa, 1199), f"final={fa[:200]!r}")
    j.check("answer_release_info",
            contains_word(fa, "2024")
            or contains_any(fa, ["no release date", "not listed", "does not list",
                                 "no specific date", "only the year", "release year"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
