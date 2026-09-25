#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--31.

Task: On Apple's website, what is the slogan for the latest Apple Watch Series.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /watch and /product/apple-watch-series-11: Apple Watch Series 11 —
    "The ultimate way to watch your health."
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
    j = Judge('Apple--31', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/apple-watch-series-11"])
           or navigated_path(t, "/watch"))
    j.check("nav_watch_series_11", nav, "expected /watch or the Series 11 page")
    j.check("answer_series11_slogan",
            contains_any(fa, ["the ultimate way to watch your health"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
