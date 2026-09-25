#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--1.

Task: Research the new features of the iOS 17 on Apple support and check its compatibility with the iPhone 12.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /support/article/ios-17-new-features lists StandBy, NameDrop, Contact
    Posters, Live Voicemail, FaceTime video messages, autocorrect; and states
    iOS 17 is compatible with iPhone XS and later, explicitly including the
    iPhone 12 (also listed in the compatible-devices table).
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
    j = Judge('Apple--1', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["ios-17", "/support"])
    j.check("nav_ios17_support", nav, "expected the iOS 17 article or the support hub")
    feats = count_named(fa, ["standby", "namedrop", "contact poster", "live voicemail",
                             "autocorrect", "facetime video message"])
    j.check("answer_two_ios17_features", feats >= 2, f"features matched={feats}")
    j.check("answer_mentions_iphone12", contains_all(fa, ["iphone 12"]), f"final={fa[:200]!r}")
    j.check("answer_iphone12_compatible",
            contains_any(fa, ["compatible", "compatibility", "supported", "supports",
                              "works", "including", "can run", "can install"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
