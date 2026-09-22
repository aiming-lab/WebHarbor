#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--13.

Browse best selling black hoodies in mens size Big and Tall that is between $25 and $50 on Amazon.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The best-seller + black + $25-$50 + Big&Tall-size filter leaves exactly
    two hoodies: Amazon Essentials Men's Big & Tall Fleece Hoodie - Black $29.99
    (4.6, 24,549) and Hanes Men's Big & Tall ComfortBlend EcoSmart Hoodie -
    Black $34.99 (4.7, 24,433). Regular-size black hoodies (Champion, Adidas)
    are distractors.

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
    j = Judge('Amazon--13', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_hoodie_search", navigated_to(t, "hoodie"),
            f"urls={[u for u in urls if 'hoodie' in u.lower()][:4]}")
    j.check("nav_big_tall_filters_or_product",
            search_url_with(t, ["min_price=25"]) or search_url_with(t, ["bestseller=1"])
            or visited_product(t, "amazon-essentials-men-s-big-tall-fleece-hoodie-black")
            or visited_product(t, "hanes-men-s-big-tall-comfortblend-ecosmart-hoodie-black"),
            "price/bestseller filter or one of the two product pages")
    j.check("answer_amazon_essentials", contains_all(fa, ["amazon essentials"]), f"final={fa[:200]!r}")
    j.check("answer_hanes", contains_all(fa, ["hanes"]), f"final={fa[:200]!r}")
    j.check("answer_both_prices", price_in(fa, 29.99) and price_in(fa, 34.99), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
