#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--21.

Task: Identify the available storage options for the latest iPad Pro on the Apple website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    The current iPad Pro pages (iPad Pro M5, iPad Pro 11-inch M4, iPad Pro
    13-inch M4) all list storage options 256GB, 512GB, 1TB, 2TB.
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
    j = Judge('Apple--21', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/ipad-pro-m5", "/product/ipad-pro-11-inch-m4",
                             "/product/ipad-pro-13-inch-m4"])
           or navigated_path(t, "/ipad"))
    j.check("nav_latest_ipad_pro", nav, "expected an iPad Pro page or /ipad")
    j.check("answer_storage_options",
            contains_all(fa, ["256gb", "512gb", "1tb", "2tb"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
