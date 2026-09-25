#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--36.

Search for a children's science experiment kit on Amazon suitable for ages 8-13, with at least a 4-star rating and priced under $30.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Children's science experiment kits under $30, 4+ stars, ages 8-13 (per
    specs; Learn & Climb's card title says Ages 8-12, its spec row says 5-8 —
    recorded in the quality audit, both readings accepted here): National
    Geographic Mega Science Kit $24.99 (4.7), 4M Crystal Growing Kit $12.99
    (4.5), Scientific Explorer Mind Blowing Science Kit $19.99 (4.6), Snap
    Circuits Jr. SC-100 $24.99 (4.8), Learn & Climb Kids Science Kit $26.99
    (4.6).

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
    j = Judge('Amazon--36', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("national geographic", 24.99), ("4m crystal", 12.99),
             ("scientific explorer", 19.99), ("snap circuits", 24.99),
             ("learn & climb", 26.99), ("learn and climb", 26.99)]
    j.check("nav_science_kit_search", navigated_to(t, "science") or navigated_to(t, "kit"),
            f"urls={[u for u in urls if 'science' in u.lower() or 'kit' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_kit", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_ages_8_13",
            contains_any(fa, ["8-13", "8 to 13", "ages 8", "age 8", "8-14", "8 to 14", "8-12", "8 to 12"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_under_30",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.check("answer_rating_4_plus",
            contains_any(fa, ["4.5", "4.6", "4.7", "4.8", "4 star", "4+"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
