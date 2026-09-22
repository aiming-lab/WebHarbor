#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--22.

Search for a set of non-stick, oven-safe cookware on Amazon. The set should include at least 10 pieces and be priced under $150.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Non-stick oven-safe sets with >=10 pieces under $150: Amazon Basics
    15-piece $89.99, Farberware Classic 15-piece $99.99, GreenLife Soft Grip
    16-piece $114.99, T-fal Ultimate 12-piece $139.99. Rachael Ray's set is
    stovetop-only and Cuisinart's is 8 pieces.

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
    j = Judge('Amazon--22', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("amazon basics", 89.99, "15"), ("farberware", 99.99, "15"),
             ("greenlife", 114.99, "16"), ("t-fal", 139.99, "12")]
    j.check("nav_cookware_search", navigated_to(t, "cookware"),
            f"urls={[u for u in urls if 'cookware' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_set", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_pieces_10_plus",
            any(contains_any(fa, [c[2] + "-piece", c[2] + "-pc", c[2] + " pc"])
                or count_claim(fa, c[2], "piece")
                for c in matched) if matched else False,
            "10+ piece count quoted for the named set")
    j.check("answer_nonstick_oven_safe",
            contains_any(fa, ["non-stick", "nonstick"]) and contains_any(fa, ["oven-safe", "oven safe", "oven safe up"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
