#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--10.

Task: Find information on the latest (as of today's date) MacBook model, including its key features such as processor type, memory size, and storage capacity.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    "Latest MacBook" is anchored per-product (any one fully-correct bundle
    passes; all served pages verified): MacBook Air 13"/15" — M5, 16GB,
    256GB/512GB(/1TB), $1099/$1299, released March 12, 2025; MacBook Pro 14"
    — M5, 24GB, 512GB(/1TB/2TB), $1699, released November 8, 2024; MacBook
    Pro 16" — M5 Pro/Max, 36GB/48GB, 512GB+, $2499; MacBook Neo — A18 Pro,
    8GB, 256GB/512GB, $599.
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
    j = Judge('Apple--10', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/macbook-air-13", "/product/macbook-air-15",
                              "/product/macbook-pro-14", "/product/macbook-pro-16",
                              "/product/macbook-neo"])
           or navigated_path(t, "/mac"))
    j.check("nav_latest_macbook", nav, "expected /mac or a MacBook product page")
    air13 = contains_all(fa, ["m5", "16gb"]) and contains_all(fa, ["256gb", "512gb"])
    air15 = contains_all(fa, ["m5", "16gb"]) and contains_word(fa, "256gb")
    mbp14 = contains_all(fa, ["m5", "24gb"]) and contains_word(fa, "512gb")
    mbp16 = contains_all(fa, ["m5"]) and contains_any(fa, ["36gb", "48gb"]) and contains_word(fa, "512gb")
    neo = contains_all(fa, ["a18 pro", "8gb"]) and contains_all(fa, ["256gb", "512gb"])
    j.check("answer_latest_macbook_bundle", air13 or air15 or mbp14 or mbp16 or neo,
            f"air13={air13} air15={air15} mbp14={mbp14} mbp16={mbp16} neo={neo} final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
