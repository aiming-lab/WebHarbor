#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--32.

Search for an electric kettle on Amazon with a capacity of at least 1.5 liters, made of stainless steel, and with a customer rating of 4 stars or above.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Stainless electric kettles >=1.5L with >=4 stars: Mueller Premium 1.8L
    $28.99 (4.6), Ovente 1.5L $29.99 (4.5), Hamilton Beach 1.7L $34.99 (4.6),
    COSORI 1.7L $39.99 (4.7), Cuisinart CPK-17 1.7L $99.95 (4.7), Breville
    BKE820XL 1.8L $149.99 (4.8). Zojirushi is 1.0L, the Fellow gooseneck is
    0.9L and rated 3.5, two kettles are plastic.

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
    j = Judge('Amazon--32', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("mueller", 28.99, "1.8"), ("ovente", 29.99, "1.5"),
             ("hamilton beach", 34.99, "1.7"), ("cosori", 39.99, "1.7"),
             ("cpk-17", 99.95, "1.7"), ("breville", 149.99, "1.8")]
    j.check("nav_kettle_search", navigated_to(t, "kettle"),
            f"urls={[u for u in urls if 'kettle' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_kettle", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_capacity_1_5l_plus",
            any(contains_any(fa, [c[2] + " liter", c[2] + "l", c[2] + " l", c[2] + "-liter", c[2] + "l"])
                for c in matched) if matched else False,
            "the named kettle's >=1.5L capacity")
    j.check("answer_stainless_4plus",
            contains_all(fa, ["stainless"]) and contains_any(fa, ["4.5", "4.6", "4.7", "4.8", "4 star", "4+"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
