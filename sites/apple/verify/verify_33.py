#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--33.

Task: Look for the color options available for the newest iMac.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    Both served iMac pages list seven colors: Blue, Green, Pink, Silver,
    Yellow, Orange, Purple ("Available in 7 colors" on the M3 page).
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
    j = Judge('Apple--33', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/imac-24"]) or navigated_path(t, "/mac"))
    j.check("nav_imac_page", nav, "expected an iMac page or /mac")
    colors = ["blue", "green", "pink", "silver", "yellow", "orange", "purple"]
    found = sum(1 for c in colors if contains_word(fa, c))
    count_ok = (number_claim(fa, "7", ["color"]) or contains_any(fa, ["seven"]))
    j.check("answer_seven_colors", count_ok or found >= 5,
            f"count_ok={count_ok} colors matched={found}")
    j.emit()


if __name__ == "__main__":
    main()
