#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--12.

Task: What Apple Repair ways are mentioned on apple website, answer 2 of them.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /support and /support/repair list the Apple Repair options: Mail-in
    repair, Carry-in repair, Onsite repair (business only), Express
    Replacement Service (and /support/repair adds Self Service Repair).
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
    j = Judge('Apple--12', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/support"])
    j.check("nav_support_pages", nav, "expected a /support page")
    opts = count_named(fa, ["mail-in", "mail in", "carry-in", "carry in",
                            "onsite", "on-site", "express replacement"])
    j.check("answer_two_repair_options", opts >= 2, f"repair options matched={opts}")
    j.emit()


if __name__ == "__main__":
    main()
