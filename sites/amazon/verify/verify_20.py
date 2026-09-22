#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--20.

Search for a wireless ergonomic keyboard with backlighting and a rating of at least 4 stars. The price should be between $40 to $60. Save the product with the 500+ customer reviews.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Backlit wireless ergonomic keyboards, >=4 stars, $40-$60, 500+ reviews:
    Logitech MX Keys $54.99 (4.8, 18,500), Perixx PERIBOARD-512 $49.99 (4.6,
    3,200), Adesso Tru-Form 450 $43.99 (4.4, 850), X9 Performance $41.99 (4.6,
    680). The non-backlit Microsoft Sculpt (22,000) and iClever (1,200) are the
    near-miss distractors. Any of the four qualifies.

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
    j = Judge('Amazon--20', a.no_llm)
    t, fa = grade_common(j, a, allowed_cart_products=(185, 186, 190, 192), allowed_wishlist_products=(185, 186, 190, 192))
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("mx keys", 54.99, ["18,500", "18500", "4.8"]),
             ("periboard", 49.99, ["3,200", "3200", "4.6"]),
             ("adesso", 43.99, ["850", "4.4"]),
             ("x9", 41.99, ["680", "4.6"])]
    j.check("nav_keyboard_search", navigated_to(t, "keyboard"),
            f"urls={[u for u in urls if 'keyboard' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_backlit_keyboard", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_backlighting",
            contains_any(fa, ["backlit", "backlight", "backlighting"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.check("answer_review_evidence",
            any(contains_any(fa, c[2]) for c in matched) if matched else False,
            "500+ review count or the matching rating quoted")
    j.emit()


if __name__ == "__main__":
    main()
