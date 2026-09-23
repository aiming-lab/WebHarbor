#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--0.

Task: Compare the prices of the latest models of MacBook Air available on Apple's website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /mac lists the current-generation MacBook Air 13" (New) at $1099.00 and
    MacBook Air 15" (New) at $1299.00; the M3 Airs are marked Previous
    generation at the same $1099 / $1299, so the price pair is stable across
    either reading of "latest".
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
    j = Judge('Apple--0', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/mac")
           or navigated_any(t, ["/product/macbook-air-13", "/product/macbook-air-15"])
           or visited_url_with(t, "/search", params_sub=[("q", "macbook")]))
    j.check("nav_macbook_air_pages", nav,
            "expected /mac or a MacBook Air product page or a macbook search")
    j.check("answer_both_air_prices",
            price_in(fa, 1099) and price_in(fa, 1299),
            f"final={fa[:200]!r}")
    j.check("answer_names_macbook_air", contains_any(fa, ["macbook air", "air 13", "air 15", "13-inch", "15-inch"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
