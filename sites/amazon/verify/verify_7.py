#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--7.

Browse the women's hiking boots on Amazon and filter the results to show only those that are waterproof and have a rating of at least 4 stars and size 6.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The waterproof / >=4 stars / size 6 filter leaves exactly four boots:
    Columbia Women's Newton Ridge Plus $89.95 (4.5), Columbia Women's Newton
    Ridge $89.99 (4.6), Merrell Women's Moab 3 $134.95 (4.7), Timberland Women's
    Mt. Maddsen $129.00 (4.5).

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
    j = Judge('Amazon--7', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_hiking_boots", navigated_to(t, "hiking") or navigated_to(t, "boot"),
            f"urls={[u for u in urls if 'hiking' in u.lower() or 'boot' in u.lower()][:4]}")
    j.check("nav_waterproof_filter_or_product",
            search_url_with(t, ["feature=waterproof"])
            or visited_product(t, "columbia-womens-newton-ridge-plus-waterproof-hiking-boot")
            or visited_product(t, "merrell-women-s-moab-3-waterproof-hiking-boot")
            or visited_product(t, "columbia-women-s-newton-ridge-waterproof-boot")
            or visited_product(t, "timberland-women-s-mt-maddsen-waterproof-boot"),
            "waterproof feature filter or a qualifying boot detail page")
    all_filters = (search_url_with(t, ["feature=waterproof"])
                   and search_url_with(t, ["min_rating=4"])
                   and search_url_with(t, ["size=6"]))
    count_ok = bool(__import__('re').search(r"(?<![\d.])4(?![\d])\s*(?:matching\s+|filtered\s+|qualifying\s+)?results",
                                            __import__('verify_lib').norm(fa)))
    j.check("answer_lists_all_four",
            (contains_all(fa, ["moab"]) and contains_all(fa, ["maddsen"])
             and __import__('verify_lib').norm(fa).count("newton ridge") >= 2)
            or (all_filters and count_ok),
            "all four filtered boots named, or all three filters applied "
            "(waterproof, 4+ stars, size 6) with the correct filtered result count")
    j.check("answer_waterproof", contains_all(fa, ["waterproof"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
