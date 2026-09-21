#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--22.

Task: Find out the trade-in value for an iPhone 13 Pro Max in good condition on the Apple website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /trade-in and /trade-in/iphone-13-pro-max: iPhone 13 Pro Max, Up to
    $440.00, Condition: good ("Good condition — no cracked screen, fully
    functional").
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
    j = Judge('Apple--22', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/trade-in"])
    j.check("nav_trade_in_page", nav, "expected a /trade-in page")
    j.check("answer_value_440", price_in(fa, 440), f"final={fa[:200]!r}")
    j.check("answer_device_named", contains_all(fa, ["iphone 13 pro max"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
