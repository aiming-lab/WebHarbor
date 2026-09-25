#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--16.

Task: Find on Apple website how many types of AirPods (3rd generation) are available and what is the price difference.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/airpods-3-lightning: From $169.00 (Lightning charging case);
    /product/airpods-3-magsafe: From $179.00 (MagSafe charging case) — two
    types, a $10 difference.
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
    j = Judge('Apple--16', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/airpods-3-lightning", "/product/airpods-3-magsafe"])
           or navigated_path(t, "/airpods"))
    j.check("nav_airpods3_pages", nav,
            "expected /airpods or an AirPods 3rd generation product page")
    j.check("answer_two_types",
            contains_word(fa, "2") or contains_any(fa, ["two"]), f"final={fa[:200]!r}")
    j.check("answer_both_prices",
            price_in(fa, 169) and price_in(fa, 179), f"final={fa[:200]!r}")
    j.check("answer_price_difference_10", contains_word(fa, "10"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
