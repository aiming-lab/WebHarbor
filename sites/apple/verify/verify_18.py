#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--18.

Task: Check if there are trade-in offers for the latest model of iPhone.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /support/article/iphone-trade-in-offers states "Yes, trade-in offers
    are currently available for the latest iPhone models" (up to $750 in
    credit); the /iphone banner confirms trade-in credit toward iPhone 17 /
    iPhone Air / iPhone 17 Pro; /trade-in lists the estimator values.
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
    j = Judge('Apple--18', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/trade-in", "iphone-trade-in-offers"])
           or navigated_path(t, "/iphone"))
    j.check("nav_trade_in_pages", nav,
            "expected /trade-in, the trade-in article, or /iphone")
    j.check("answer_affirmative_trade_in",
            contains_any(fa, ["trade"]) and contains_any(fa, ["yes", "offer"]),
            f"final={fa[:200]!r}")
    j.check("answer_not_negated",
            not contains_any(fa, ["no trade", "not available", "no offers", "there are no"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
