#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--1.

Search for women's golf polos in m size, priced between 50 to 75 dollars, and save the lowest priced among results.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Three qualifying polos (size M, $50-$75): Women's IZOD SwingFlex Golf Polo
    $52.00, Women's Classic Pique Golf Polo $55.00, Women's Under Armour Playoff
    Golf Polo $69.99. Lowest priced = the IZOD SwingFlex at $52.00.

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
    j = Judge('Amazon--1', a.no_llm)
    t, fa = grade_common(j, a, allowed_cart_products=(336,), allowed_wishlist_products=(336,))
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_golf_polo_search", navigated_to(t, "polo"),
            f"urls={[u for u in urls if 'polo' in u.lower()][:4]}")
    j.check("nav_filters_or_product",
            visited_product(t, "women-s-izod-swingflex-golf-polo")
            or search_url_with(t, ["size=m"]) or search_url_with(t, ["min_price=50"])
            or search_url_with(t, ["max_price=75"]),
            "IZOD product page or size/price-filtered search")
    j.check("answer_izod_swingflex", contains_any(fa, ["izod", "swingflex"]), f"final={fa[:200]!r}")
    j.check("answer_lowest_price_52", price_in(fa, 52.00), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
