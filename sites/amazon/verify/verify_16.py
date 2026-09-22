#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--16.

Find the Return Policy for Mens Rhinestone Skull Graphic Shirt on Amazon. Color: Black, Size: XX-Large. If Free return is avaliable, tell me how to return this item.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Target product: Men's Rhinestone Skull Graphic T-Shirt (Black, sizes up
    to 3X-Large incl. XX-Large), $34.99. Its detail page shows 'FREE Returns -
    Return this item for free within 30 days' and the policy text: returnable
    within 30 days of delivery, free return with the prepaid Amazon return
    shipping label provided in Your Orders, item in new/unworn condition with
    tags attached. The Gothic/Flaming/Bling/Skull-Crown variants carry
    different policies and are distractors.

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
    j = Judge('Amazon--16', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_rhinestone_search", navigated_to(t, "rhinestone"),
            f"urls={[u for u in urls if 'rhinestone' in u.lower()][:4]}")
    j.check("nav_target_product_page",
            visited_product(t, "men-s-rhinestone-skull-graphic-t-shirt-black"),
            "the plain Rhinestone Skull Graphic T-Shirt page (not Gothic/Flaming/Bling/Skull-Crown)")
    j.check("answer_free_return_available",
            contains_any(fa, ["free return", "free returns", "no cost", "at no cost"]),
            f"final={fa[:260]!r}")
    j.check("answer_30_day_window",
            contains_any(fa, ["30 day", "30-day", "within 30", "30 days"]), f"final={fa[:260]!r}")
    j.check("answer_how_to_return",
            contains_any(fa, ["prepaid", "your orders", "shipping label", "return label", "ship it back"]),
            "how-to: prepaid label from Your Orders / ship it back")
    j.emit()


if __name__ == "__main__":
    main()
