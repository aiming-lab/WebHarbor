#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--4.

Task: How much does it cost to buy a Macbook pro, 16-inch, Apple M3 Max chip with 16-core CPU, 40-core GPU, 64GB unified memory, 1TB SSD.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/macbook-pro-16-inch-m3-max is the exact configuration (M3 Max,
    16-core CPU, 40-core GPU, 64GB unified memory, 1TB SSD): From $4299.00.
    The /mac listing card for that configuration shows the same From
    $4299.00 price, so either page honestly carries the answer.
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
    j = Judge('Apple--4', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/product/macbook-pro-16-inch-m3-max")
           or navigated_path(t, "/mac"))
    j.check("nav_mbp16_m3max_page", nav,
            "expected /product/macbook-pro-16-inch-m3-max or the /mac listing")
    j.check("answer_price_4299", price_in(fa, 4299), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
