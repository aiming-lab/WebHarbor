#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--19.

Task: On Apple's website, what is the slogan for the Mac and what is the slogan for the Macbook pro.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    Mac slogan "If you can dream it, Mac can do it." — on /product/mac (Slogan
    row and description) and on the /mac and /shop listing cards for Mac.
    MacBook Pro taglines/slogans on the mirror: "Mind-blowing.
    Head-turning." (Slogan row of the M3-generation MBP pages and the home
    MacBook Pro card), "Outrageously powerful." (MBP 14"/14-inch M3),
    "The most powerful MacBook Pro ever." (MBP 16"/16-inch M3 Max), and
    "The Pro laptop, reimagined." (MBP 14/16-inch M3 Pro cards on /mac,
    /shop, compare, and search).
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
    j = Judge('Apple--19', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/product/mac") or navigated_path(t, "/mac")
           or navigated_path(t, "/shop"))
    j.check("nav_mac_slogan_page", nav,
            "expected /product/mac or a listing (/mac, /shop) carrying the Mac slogan")
    j.check("answer_mac_slogan",
            contains_all(fa, ["if you can dream it", "mac can do it"]),
            f"final={fa[:200]!r}")
    j.check("answer_macbook_pro_slogan",
            contains_any(fa, ["mind-blowing", "mind blowing", "outrageously powerful",
                              "the most powerful macbook pro ever",
                              "the pro laptop, reimagined"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
