#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--13.

Task: How many colors does the latest MacBook Air come in?

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    Every served MacBook Air page (13", 15", 13-inch M3, 15-inch M3) lists
    the same four colors: Midnight, Starlight, Space Gray, Silver.
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
    j = Judge('Apple--13', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/macbook-air-13", "/product/macbook-air-15",
                              "/product/macbook-air-13-inch-m3", "/product/macbook-air-15-inch-m3"])
           or navigated_path(t, "/mac"))
    j.check("nav_macbook_air_page", nav, "expected /mac or a MacBook Air product page")
    count_ok = (number_claim(fa, "4", ["color"])
                or contains_any(fa, ["four color", "four colours"]))
    listed_ok = contains_all(fa, ["midnight", "starlight", "space gray", "silver"])
    j.check("answer_four_colors", count_ok or listed_ok,
            f"count_ok={count_ok} listed_ok={listed_ok} final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
