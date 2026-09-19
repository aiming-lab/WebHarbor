#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--30.

Locate the highest-rated fiction book released in 2024 on Amazon, with a minimum of 50 customer reviews.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    2024 fiction with >=50 reviews, sorted by rating: #1 'The Women' 4.9
    stars (56,000 reviews, $18.99, released 2024-01-15). Fourth Wing and Demon
    Copperhead are 4.8, Yellowface 4.5, The Heaven & Earth Grocery Store 4.7.

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
    j = Judge('Amazon--30', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_fiction_2024",
            navigated_to(t, "fiction") or visited_product(t, "the-women")
            or search_url_with(t, ["year=2024"]),
            f"urls={[u for u in urls if 'fiction' in u.lower() or 'book' in u.lower()][:4]}")
    j.check("answer_the_women", contains_all(fa, ["the women"]), f"final={fa[:200]!r}")
    j.check("answer_highest_rating_4_9", contains_any(fa, ["4.9"]), f"final={fa[:200]!r}")
    j.check("answer_2024_release", contains_any(fa, ["2024"]), f"final={fa[:200]!r}")
    j.check("answer_review_count_or_price",
            contains_any(fa, ["56,000", "56000", "18.99"]) or price_in(fa, 18.99), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
