#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--40.

Locate a women's yoga mat in purple, with a thickness of at least 5mm, rated 4+ stars, and priced under $30 on Amazon. Check how many colors are available in total, and what is the return and delivery policy.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Purple yoga mats >=5mm, 4+ stars, under $30 (the mirror's search cannot
    separate women's-tagged from unisex purple mats, so both families count):
    Gaiam Essentials 6mm purple $19.99 (10 colors), BalanceFrom GoYoga 12mm
    purple $21.99 (10 colors), Amazon Basics Yoga Mat 12mm purple $18.99 (10
    colors), IUGA 6mm purple $28.99 (10 colors), Heathyoga 6mm purple $29.99
    (10 colors), Tumaz 8mm plum purple $25.99 (11 colors), plus the unisex
    purple mats Gaiam 10mm $24.99 (5 colors), BalanceFrom All-Purpose 12mm
    $22.99 (5 colors), Amazon Basics Exercise 13mm $19.99 (5 colors). All
    carry '30-day free returns / FREE Returns within 30 days' and FREE delivery
    (the women's mats say 'FREE delivery Wednesday, Apr 16'). The claimed total
    color count must match the mat the answer identifies.

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
    j = Judge('Amazon--40', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [
        (["gaiam"], 19.99, 10, "gaiam-essentials-yoga-mat-6mm-purple"),
        (["balancefrom"], 21.99, 10, "balancefrom-goyoga-yoga-mat-1-2-inch-12mm-purple"),
        (["amazon basics"], 18.99, 10, "amazon-basics-yoga-mat-1-2-inch-purple"),
        (["iuga"], 28.99, 10, "iuga-yoga-mat-6mm-non-slip-purple"),
        (["heathyoga"], 29.99, 10, "heathyoga-eco-friendly-yoga-mat-6mm-purple"),
        (["tumaz"], 25.99, 11, "tumaz-yoga-mat-8mm-plum-purple"),
        (["gaiam"], 24.99, 5, "gaiam-essentials-thick-yoga-mat-2-5-inch-10mm"),
        (["balancefrom"], 22.99, 5, "balancefrom-goyoga-all-purpose-1-2-inch-yoga-mat-12mm"),
        (["amazon basics"], 19.99, 5, "amazon-basics-extra-thick-exercise-yoga-mat-13mm"),
    ]
    j.check("nav_purple_yoga_mat",
            navigated_to(t, "yoga") and navigated_to(t, "purple"),
            f"urls={[u for u in urls if 'yoga' in u.lower() and 'purple' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, c[0]) and price_in(fa, c[1])]
    j.check("answer_qualifying_mat", bool(matched),
            f"matched={[(c[0], c[1]) for c in matched]} of {[(c[0], c[1]) for c in CANDS]}")
    claimed = extract_color_count_claim(fa)
    allowed = sorted({c[2] for c in matched})
    j.check("answer_color_count_matches_product",
            claimed in allowed if matched else False,
            f"claimed total colors={claimed}, allowed for the named mat={allowed}")
    j.check("answer_return_policy",
            contains_any(fa, ["free return", "free returns", "30 day", "30-day", "30 days"]),
            f"final={fa[:260]!r}")
    j.check("answer_delivery_policy",
            contains_any(fa, ["free delivery", "free shipping", "2 day", "two day", "apr 16", "april 16"]),
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
