#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--8.

Task: Identify and list the specifications of the latest iPad model released by Apple, including its storage options, processor type, and display features.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    "Latest iPad" is anchored per-product (any one fully-correct bundle
    passes; all served pages verified): iPad Pro M5 — M5 chip, 11"/13"
    Ultra Retina XDR, storage 256GB/512GB/1TB/2TB, From $999; iPad Air M4 —
    M4 chip, 11"/13" Liquid Retina, storage 128GB/256GB/512GB/1TB, From
    $599; iPad Pro 11/13-inch M4 — M4 chip, Ultra Retina XDR, storage
    256GB/512GB/1TB/2TB, From $999 / $1299.
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
    j = Judge('Apple--8', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/product/ipad-pro-m5", "/product/ipad-air-m4",
                             "/product/ipad-pro-11-inch-m4", "/product/ipad-pro-13-inch-m4"])
           or navigated_path(t, "/ipad"))
    j.check("nav_latest_ipad", nav, "expected an iPad product page or /ipad")
    pro_m5 = (contains_all(fa, ["m5", "ultra retina xdr"])
              and contains_all(fa, ["256gb", "512gb", "1tb", "2tb"]))
    air_m4 = (contains_all(fa, ["m4", "liquid retina"])
              and contains_all(fa, ["128gb", "256gb", "512gb", "1tb"]))
    pro_m4 = (contains_all(fa, ["m4", "ultra retina xdr"])
              and contains_all(fa, ["256gb", "512gb", "1tb", "2tb"]))
    j.check("answer_latest_ipad_bundle", pro_m5 or air_m4 or pro_m4,
            f"pro_m5={pro_m5} air_m4={air_m4} pro_m4={pro_m4} final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
