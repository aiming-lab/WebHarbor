#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--39.

Locate a travel guide book on Amazon for Japan, published in 2024, with at least 20 customer reviews.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Japan travel guides published 2024 with >=20 reviews: Lonely Planet Japan
    (Travel Guide) 2024 edition $22.99 (4.8, 850 reviews), Japan Travel Guide:
    The Complete Insider's Guide $19.99 (4.5, 180 reviews), National Geographic
    Traveler Japan $27.99 (4.6, 95 reviews).

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
    j = Judge('Amazon--39', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("lonely planet", 22.99, ["850"]), ("insider", 19.99, ["180"]),
             ("national geographic traveler", 27.99, ["95"])]
    j.check("nav_japan_guide_search",
            navigated_to(t, "japan") or navigated_to(t, "travel guide"),
            f"urls={[u for u in urls if 'japan' in u.lower() or 'guide' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_guide", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_published_2024", contains_any(fa, ["2024"]), f"final={fa[:200]!r}")
    j.check("answer_reviews_20_plus",
            any(contains_any(fa, c[2]) for c in matched) if matched else False,
            "the named guide's >=20 review count")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
