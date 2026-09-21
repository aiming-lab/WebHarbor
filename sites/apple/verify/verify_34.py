#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--34.

Task: Identify the size and weight for the Apple TV 4K and list the Siri Remote features introduced.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /product/apple-tv-4k specs: Size 93 x 93 x 31 mm; Weight 208 grams
    (Wi-Fi), 214 grams (Wi-Fi + Ethernet); Siri remote features:
    Touch-enabled clickpad, Find My, USB-C, Back button, Power button,
    Mute button, Siri, Dedicated TV app button.
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
    j = Judge('Apple--34', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_path(t, "/product/apple-tv-4k")
    j.check("nav_apple_tv_page", nav, "expected /product/apple-tv-4k")
    j.check("answer_weight_208g", contains_word(fa, "208"), f"final={fa[:200]!r}")
    j.check("answer_size_93mm", contains_word(fa, "93"), f"final={fa[:200]!r}")
    feats = ["clickpad", "find my", "usb-c", "power button", "mute", "siri",
             "back button", "tv app button"]
    found = sum(1 for f in feats if contains_any(fa, [f]))
    j.check("answer_three_remote_features", found >= 3, f"remote features matched={found}")
    j.emit()


if __name__ == "__main__":
    main()
