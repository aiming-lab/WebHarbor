#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--15.

Task: On Apple's website, how many different types of keyboards are available when customizing your 14-inch MacBook Pro?

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /configure/macbook-pro-14-inch-m3 and /configure/macbook-pro-14 both list
    exactly 4 keyboard layouts (US English, British English, Spanish,
    French); the product pages state "4 keyboard layouts available".
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
    j = Judge('Apple--15', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/configure/macbook-pro-14-inch-m3",
                            "/product/macbook-pro-14-inch-m3",
                            "/configure/macbook-pro-14", "/product/macbook-pro-14"])
    j.check("nav_mbp14_config", nav,
            "expected a 14-inch MacBook Pro configurator or product page")
    j.check("answer_four_keyboards",
            number_claim(fa, "4", ["keyboard", "layout"])
            or contains_any(fa, ["four keyboard", "four layout"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
