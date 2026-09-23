#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--14.

Task: Identify the upgrade options available for the cheapest base model of the MacBook Pro 14-inch with M3 chip, and calculate the total price difference from the base model to the maximum upgrade (no Pre-Installed Software) offered by Apple.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /configure/macbook-pro-14-inch-m3 (base $1599.00): Memory 8GB (Included),
    16GB +$200, 24GB +$400; Storage 512GB (Included), 1TB +$200; Software
    None (Included), Final Cut Pro +$299.99, Logic Pro +$199.99; Keyboard 4
    layouts ($0). Maximum upgrade excluding software = 24GB + 1TB = +$600
    ($1599 -> $2199).
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
    j = Judge('Apple--14', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/configure/macbook-pro-14-inch-m3", "/product/macbook-pro-14-inch-m3"])
    j.check("nav_mbp14_m3_config", nav,
            "expected /configure/macbook-pro-14-inch-m3 or its product page")
    j.check("answer_upgrade_options",
            contains_any(fa, ["16gb", "24gb"]) and contains_any(fa, ["1tb", "512gb"]),
            f"final={fa[:200]!r}")
    j.check("answer_upgrade_prices",
            price_in(fa, 200) or price_in(fa, 400), f"final={fa[:200]!r}")
    j.check("answer_total_delta_600", contains_word(fa, "600"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
