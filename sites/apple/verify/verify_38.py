#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--38.

Task: Explore accessories for Apple Vision Pro, list at least three accessories.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /vision-pro lists the Vision Pro Accessories: Apple Vision Pro Travel
    Case ($199), Apple Vision Pro Battery Pack ($199), Apple Vision Pro
    Light Seal ($199); /accessories additionally shows the Dual Loop Band,
    Solo Knit Band ($99) and ZEISS Optical Inserts ($149).
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
    j = Judge('Apple--38', a.no_llm)
    t, fa = grade_common(j, a)
    nav = (navigated_any(t, ["/vision-pro", "/product/apple-vision-pro",
                              "/product/vision-pro-", "/product/apple-vision-pro-"])
           or navigated_path(t, "/accessories")
           or visited_url_with(t, "/search", params_sub=[("q", "vision pro")]))
    j.check("nav_vision_pro_accessories", nav,
            "expected /vision-pro, /accessories, a Vision Pro accessory page, "
            "or a vision-pro search")
    accs = ["travel case", "battery pack", "light seal", "solo knit band",
            "dual loop band", "zeiss", "optical insert"]
    found = sum(1 for a in accs if contains_any(fa, [a]))
    j.check("answer_three_accessories", found >= 3, f"accessories matched={found}")
    j.emit()


if __name__ == "__main__":
    main()
