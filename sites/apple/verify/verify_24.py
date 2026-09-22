#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--24.

Task: Find out the starting price for the most recent model of the iMac on the Apple website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    Both served iMac pages (iMac 24" M5 and iMac 24-inch M3) show From
    $1299.00.
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
    j = Judge('Apple--24', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/imac-24"]) or navigated_path(t, "/mac"))
    j.check("nav_imac_page", nav, "expected an iMac page or /mac")
    j.check("answer_price_1299", price_in(fa, 1299), f"final={fa[:200]!r}")
    j.check("answer_names_imac", contains_any(fa, ["imac"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
