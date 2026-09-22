#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--40.

Task: Find information on Apple website, and tell me the device weight of Apple Vision Pro and list 5 Built-in Apps it supports.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /vision-pro and /product/apple-vision-pro: "Weight: 600 to 650 grams
    (depending on Light Seal and band)"; Built-in Apps: Safari, Photos,
    Music, Messages, Apple TV, FaceTime, Notes, Mail, Keynote, Freeform.
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
    j = Judge('Apple--40', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_any(t, ["/vision-pro", "/product/apple-vision-pro"])
    j.check("nav_vision_pro", nav, "expected /vision-pro or /product/apple-vision-pro")
    j.check("answer_weight_600_650",
            contains_word(fa, "600") and contains_word(fa, "650"), f"final={fa[:200]!r}")
    apps = ["safari", "photos", "music", "messages", "apple tv", "facetime",
            "notes", "mail", "keynote", "freeform"]
    found = sum(1 for a in apps if contains_any(fa, [a]))
    j.check("answer_five_builtin_apps", found >= 5, f"built-in apps matched={found}")
    j.emit()


if __name__ == "__main__":
    main()
