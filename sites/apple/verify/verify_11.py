#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--11.

Task: Get information about the latest iPad model released by Apple, including its release date, base storage capacity, and starting price.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    Release dates on the served iPad pages pin the answer per-product (any
    one fully-correct bundle passes): iPad Pro M5 — October 15, 2025, 256GB,
    $999; iPad Air M4 — May 15, 2024, 128GB, $599; iPad Pro 11-inch M4 —
    May 15, 2024, 256GB, $999; iPad Pro 13-inch M4 — May 15, 2024, 256GB,
    $1299.
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
    j = Judge('Apple--11', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/ipad-pro-m5", "/product/ipad-air-m4",
                             "/product/ipad-pro-11-inch-m4", "/product/ipad-pro-13-inch-m4"])
           or navigated_path(t, "/ipad"))
    j.check("nav_latest_ipad", nav, "expected an iPad product page or /ipad")
    pro_m5 = contains_all(fa, ["october 15, 2025", "256gb"]) and price_in(fa, 999)
    air_m4 = contains_all(fa, ["may 15, 2024", "128gb"]) and price_in(fa, 599)
    p11 = contains_all(fa, ["may 15, 2024", "256gb"]) and price_in(fa, 999)
    p13 = contains_all(fa, ["may 15, 2024", "256gb"]) and price_in(fa, 1299)
    j.check("answer_release_date_storage_price", pro_m5 or air_m4 or p11 or p13,
            f"pro_m5={pro_m5} air_m4={air_m4} p11={p11} p13={p13} final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
