#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--25.

Task: On the Apple website, look up the processor for the latest model of the Apple TV.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/apple-tv-4k (the only Apple TV): Chip A15 Bionic / Processor
    A15 Bionic.
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
    j = Judge('Apple--25', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_path(t, "/product/apple-tv-4k")
    j.check("nav_apple_tv_page", nav, "expected /product/apple-tv-4k")
    j.check("answer_a15_processor", contains_any(fa, ["a15"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
