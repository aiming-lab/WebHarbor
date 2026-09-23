#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--28.

Task: On Apple's website, find out if the Mac Mini can be configured with a GPU larger than 16-core.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/mac-mini-m2-pro specs: "GPU: 16-core GPU", "Gpu: up to
    19-core GPU", "Max gpu: Configurable up to 19-core GPU (larger than
    16-core)" — yes, configurable up to a 19-core GPU.
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
    j = Judge('Apple--28', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/mac-mini-m2-pro"])
           or navigated_path(t, "/mac")
           or visited_url_with(t, "/search", params_sub=[("q", "mac mini")]))
    j.check("nav_mac_mini_page", nav, "expected the Mac mini page, /mac, or a mac-mini search")
    j.check("answer_19core_gpu", contains_word(fa, "19") and contains_any(fa, ["gpu", "core"]),
            f"final={fa[:200]!r}")
    j.check("answer_affirmative",
            contains_any(fa, ["yes", "can", "configur", "up to", "support"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
