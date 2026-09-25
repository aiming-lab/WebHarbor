#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--42.

Task: Find updates for Apple Watch Series 7,8,9 on Apple's website.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /support/article/apple-watch-series-7-8-9-updates ("watchOS updates
    for Apple Watch Series 7, 8, and 9"): Series 7, 8, and 9 all support
    the watchOS 10 update; to update, open the Watch app on iPhone > My
    Watch > General > Software Update. The support hub shows the same
    summary.
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
    j = Judge('Apple--42', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["apple-watch-series-7-8-9", "/support", "/watch",
                            "/product/apple-watch-series-7", "/product/apple-watch-series-8",
                            "/product/apple-watch-series-9"])
    j.check("nav_watch_updates", nav,
            "expected the watch-updates article, /support, /watch, or a Series 7/8/9 page")
    j.check("answer_watchos_10",
            contains_any(fa, ["watchos"]) and contains_word(fa, "10"),
            f"final={fa[:200]!r}")
    j.check("answer_series_789",
            contains_any(fa, ["series 7", "7, 8", "7, 8, and 9", "series 8", "series 9"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
