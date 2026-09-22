#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--14.

Find the new surge protector on Amazon with 6 to 8 outlets under 25 dollars with customer reviews above 4+ stars.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Qualifying surge protectors (6-8 outlets, <$25, 4+ stars, New): Philips
    6-outlet $12.99, AmazonBasics 6-outlet $14.99, Belkin 8-outlet $19.99,
    Anker PowerStrip 6-outlet $21.99, Monster 6-outlet $22.49, Kensington
    8-outlet $23.99. APC/Tripp Lite cost more, CyberPower has 12 outlets, GE
    (3.9) and Woods (3.8) are under 4 stars.

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
    j = Judge('Amazon--14', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("philips", 12.99), ("amazonbasics", 14.99), ("belkin", 19.99),
             ("anker powerstrip", 21.99), ("monster", 22.49), ("kensington", 23.99)]
    j.check("nav_surge_search", navigated_to(t, "surge"),
            f"urls={[u for u in urls if 'surge' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_protector", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.check("answer_outlet_or_rating_evidence",
            contains_any(fa, ["outlet", "outlets"]) or contains_any(fa, ["4.5", "4.6", "4.7", "4+"]),
            "outlet count or the 4+ star rating quoted")
    j.emit()


if __name__ == "__main__":
    main()
