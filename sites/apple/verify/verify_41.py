#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--41.

Task: How much does it cost to buy an ipad mini with 64GB storage and Wi-Fi + Cellular connectivity? (no engraving, no apple pencil, no smart folio, no apple trade-in).

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/ipad-mini-64gb-wi-fi-cellular ("iPad mini", 64GB, Wi-Fi +
    Cellular): From $649.00. The /ipad listing card for that variant ("Mega
    power. Mini sized. Wi-Fi + Cellular.") shows the same From $649.00, so
    the listing honestly carries the answer too.
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
    j = Judge('Apple--41', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/ipad-mini-64gb-wi-fi-cellular", "/product/ipad-mini"])
           or visited_url_with(t, "/search", params_sub=[("q", "ipad mini")])
           or navigated_path(t, "/ipad"))
    j.check("nav_ipad_mini_pages", nav,
            "expected an iPad mini product page, an ipad-mini search, or /ipad")
    j.check("answer_price_649", price_in(fa, 649), f"final={fa[:200]!r}")
    j.check("answer_names_ipad_mini", contains_any(fa, ["ipad mini"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
