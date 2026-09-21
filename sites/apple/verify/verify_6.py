#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--6.

Task: Find AirPods on Apple and how many types are currently available.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /airpods lists exactly 7 AirPods products: AirPods Pro 3, AirPods Max 2,
    AirPods 4, AirPods 3rd generation (Lightning), AirPods 3rd generation
    (MagSafe), AirPods Pro (2nd generation), AirPods (2nd generation).
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
    j = Judge('Apple--6', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/airpods")
           or visited_url_with(t, "/search", params_sub=[("q", "airpods")]))
    j.check("nav_airpods_listing", nav, "expected /airpods or an airpods search")
    j.check("answer_seven_types",
            contains_word(fa, "7") or contains_any(fa, ["seven"]),
            f"final={fa[:200]!r}")
    j.check("answer_about_airpods", contains_any(fa, ["airpods", "air pods"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
