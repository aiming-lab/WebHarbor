#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--28.

Search for a yoga mat on Amazon that is at least 6mm thick, non-slip, and eco-friendly. The price should be under $50.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Eco-friendly non-slip yoga mats >=6mm under $50: IUGA Eco-Friendly Yoga
    Mat 6mm $34.99, Amazon Basics Yoga Mat 12mm (purple) $18.99, Gaiam
    Essentials 6mm (purple) $19.99, Tumaz 8mm (plum purple) $25.99, BalanceFrom
    GoYoga 12mm (purple) $21.99, IUGA 6mm (purple) $28.99, Heathyoga 6mm
    (purple) $29.99. The PVC/NBR mats (Gaiam 10mm unisex, BalanceFrom
    All-Purpose, Amazon Basics Exercise) are not eco-friendly; travel mats are
    thinner than 6mm.

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
    j = Judge('Amazon--28', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("iuga", 34.99, "6mm"), ("iuga", 28.99, "6mm"), ("heathyoga", 29.99, "6mm"),
             ("tumaz", 25.99, "8mm"), ("gaiam", 19.99, "6mm"), ("balancefrom", 21.99, "12mm"),
             ("amazon basics", 18.99, "12mm")]
    j.check("nav_yoga_mat_search", navigated_to(t, "yoga"),
            f"urls={[u for u in urls if 'yoga' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]]) and price_in(fa, c[1])]
    j.check("answer_qualifying_mat", bool(matched),
            f"matched={[(c[0], c[1]) for c in matched]} of {[(c[0], c[1]) for c in CANDS]}")
    j.check("answer_thickness_6mm_plus",
            any(contains_any(fa, [c[2], c[2].replace("mm", " mm"), c[2] + " thick"]) for c in matched)
            if matched else False,
            "the named mat's >=6mm thickness")
    j.check("answer_eco_friendly_non_slip",
            contains_any(fa, ["eco-friendly", "eco friendly"]) and contains_any(fa, ["non-slip", "non slip", "nonslip"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
