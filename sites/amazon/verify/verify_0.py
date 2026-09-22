#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--0.

Search an Xbox Wireless controller with green color and rated above 4 stars.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Exactly one qualifying product exists: Xbox Wireless Controller (Velocity
    Green), $64.99, 4.7 stars, 28,430 reviews. The green 'Mineral Camo' variant
    is rated 3.8 (fails the star floor), all other Xbox controllers are not green.

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
    j = Judge('Amazon--0', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_xbox_search", navigated_to(t, "xbox"),
            f"urls={[u for u in urls if 'xbox' in u.lower()][:4]}")
    j.check("nav_green_or_rating_filter_or_product",
            visited_product(t, "xbox-wireless-controller-velocity-green")
            or search_url_with(t, ["xbox", "color=green"])
            or search_url_with(t, ["xbox", "min_rating=4"]),
            "velocity-green product page or green/rating-filtered search")
    j.check("answer_xbox_green_controller",
            contains_all(fa, ["xbox wireless controller"]) and contains_any(fa, ["velocity green", "green"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_64_99", price_in(fa, 64.99), f"final={fa[:200]!r}")
    j.check("answer_rating_evidence",
            contains_any(fa, ["4.7", "28,430", "28430", "above 4", "over 4", "more than 4"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
