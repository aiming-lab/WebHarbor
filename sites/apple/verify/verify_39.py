#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--39.

Task: Find solutions on Apple's website if you forgot your Apple ID password.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /support/apple-id-forgot-password ("If you forgot your Apple ID
    password"): reset on the web at iforgot.apple.com, or on iPhone/iPad/
    Apple Watch Settings > [your name] > Sign-In & Security > Change
    Password, or on Mac System Settings > [your name] > Sign-In & Security
    > Change Password; the support hub shows the same summary.
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
    j = Judge('Apple--39', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/support"])
    j.check("nav_support_pages", nav, "expected a /support page")
    j.check("answer_reset_solution",
            contains_any(fa, ["iforgot"])
            or (contains_any(fa, ["settings", "system settings"])
                and contains_any(fa, ["change password"])),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
