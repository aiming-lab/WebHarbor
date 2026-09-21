#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--6.

Browse black strollers within $100 to $200 on Amazon. Then find one Among these black strollers with over 20,000 reviews and a rating greater than 4 star.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Black strollers $100-$200 with >20,000 reviews and >4 stars: Chicco Bravo
    Trio Travel System - Poetic Black $179.99 (4.7, 28,760), Joovy Scooter X2
    Double Stroller - Black $189.99 (4.7, 25,400), Britax B-Lively Lightweight
    Stroller - Raven $199.99 (4.6, 21,100). Any one of the three qualifies.

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
    j = Judge('Amazon--6', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [
        ("chicco bravo", 179.99, ["28,760", "28760", "4.7"]),
        ("joovy scooter", 189.99, ["25,400", "25400", "4.7"]),
        ("britax b-lively", 199.99, ["21,100", "21100", "4.6"]),
    ]
    j.check("nav_stroller_search", navigated_to(t, "stroller"),
            f"urls={[u for u in urls if 'stroller' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_all(fa, [c[0]])]
    j.check("answer_names_qualifying_stroller", bool(matched),
            f"matched={[c[0] for c in matched]} of {([c[0] for c in CANDS])}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False,
            f"final={fa[:200]!r}")
    j.check("answer_reviews_or_rating_evidence",
            any(contains_any(fa, c[2]) for c in matched) if matched else False,
            "20k+ review count or the matching star rating quoted")
    j.emit()


if __name__ == "__main__":
    main()
