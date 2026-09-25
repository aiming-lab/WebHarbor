#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--35.

Task: How many types of Apple Pencil are currently available on the Apple's website? Which one supports Wireless pairing and charging.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /accessories lists four Apple Pencil types: Apple Pencil Pro, Apple
    Pencil (2nd generation), Apple Pencil (USB-C), Apple Pencil (1st
    generation). Wireless pairing and charging: Apple Pencil Pro
    ("Wireless pairing and wireless charging") and Apple Pencil (2nd
    generation) ("Wireless pairing, wireless charging"); the USB-C model
    explicitly does not support wireless charging.
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
    j = Judge('Apple--35', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_path(t, "/accessories")
           or navigated_any(t, ["/product/apple-pencil"])
           or visited_url_with(t, "/search", params_sub=[("q", "apple pencil")]))
    j.check("nav_pencil_pages", nav,
            "expected /accessories, an Apple Pencil page, or an apple-pencil search")
    j.check("answer_four_types",
            contains_word(fa, "4") or contains_any(fa, ["four"]), f"final={fa[:200]!r}")
    j.check("answer_wireless_pairing_charging",
            contains_any(fa, ["wireless"])
            and contains_any(fa, ["pairing", "charging", "charge"]),
            f"final={fa[:200]!r}")
    j.check("answer_which_pencil",
            contains_any(fa, ["pro", "2nd generation", "second generation"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
