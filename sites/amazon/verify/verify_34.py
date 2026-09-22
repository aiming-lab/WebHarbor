#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--34.

Find a beginner's acrylic paint set on Amazon, with at least 24 colors, suitable for canvas painting, and priced under $40.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Acrylic paint sets with >=24 colors, canvas-suitable, under $40: Crayola
    Washable Paint Set 40 colors $15.99, Ohuhu Acrylic Paint Set 36 colors
    $22.99, Magicfly Acrylic Paint Set 32 colors $24.99, Castle Art Supplies
    24 colors $29.99. Liquitex Basics has only 12 colors.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (anonymous carts are cookie-backed, so an honest
run leaves the instance DB identical to its seed).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_product,
                        visited_root, search_url_with, contains_all, contains_any,
                        price_in, first_mention, mentions_percent_for, count_claim,
                        extract_color_count_claim, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('Amazon--34', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("castle art", 29.99, "24"), ("magicfly", 24.99, "32"),
             ("ohuhu", 22.99, "36"), ("crayola", 15.99, "40")]
    j.check("nav_paint_search", navigated_to(t, "paint"),
            f"urls={[u for u in urls if 'paint' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_set", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_colors_24_plus",
            any(count_claim(fa, c[2], "color") for c in matched) if matched else False,
            "the named set's >=24 color count")
    j.check("answer_canvas_suitable",
            contains_any(fa, ["canvas"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
