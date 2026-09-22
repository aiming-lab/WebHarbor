#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--15.

Find a pair of mens running shoes in black, size 7, 4+ stars and under $50 and add them to my cart on Amazon.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Black size-7 4+star running shoes under $50: ASICS Men's Gel-Contend 7
    Running Shoe $47.99 (4.6) and Skechers Men's Go Walk Max Running Shoe $42.99
    (4.5). All other black size-7 running shoes cost $52.99-$64.99. Anonymous
    add-to-cart is cookie-backed and redirects to /bag (DB stays at seed).

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
    j = Judge('Amazon--15', a.no_llm)
    t, fa = grade_common(j, a, allowed_cart_products=(160, 161))
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("asics", "asics-men-s-gel-contend-7-running-shoe-black", 47.99),
             ("skechers", "skechers-men-s-go-walk-max-running-shoe-black", 42.99)]
    j.check("nav_running_shoes", navigated_to(t, "running shoe") or navigated_to(t, "running+shoe"),
            f"urls={[u for u in urls if 'running' in u.lower()][:4]}")
    j.check("nav_product_or_filters",
            any(visited_product(t, c[1]) for c in CANDS)
            or search_url_with(t, ["size=7"]) or search_url_with(t, ["max_price=50"]),
            "a qualifying shoe page or size/price filters")
    j.check("cart_add_evidence", navigated_to(t, "/bag"), "add-to-cart redirects to /bag")
    matched = [c for c in CANDS if contains_all(fa, [c[0]])]
    j.check("answer_qualifying_shoe", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_price_matches",
            any(price_in(fa, c[2]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
