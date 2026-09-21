#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--21.

Find a stainless steel, 12-cup programmable coffee maker on Amazon. The price range should be between $100 to $200. Report the one with the 4+ customer rating.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    12-cup programmable stainless coffee makers $100-$200 with 4+ rating:
    Hamilton Beach Programmable $109.99 (4.5), Ninja CE251 $119.99 (4.6), Braun
    KF7175 BrewSense $134.99 (4.7), OXO Brew 12-Cup $199.99 (4.7). The
    Cuisinart DCC-3200P1 is 14-cup; the Keurig K-Elite is single-serve.

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
    j = Judge('Amazon--21', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("hamilton beach", 109.99, "4.5"), ("ninja ce251", 119.99, "4.6"),
             ("braun", 134.99, "4.7"), ("oxo", 199.99, "4.7")]
    j.check("nav_coffee_maker_search", navigated_to(t, "coffee"),
            f"urls={[u for u in urls if 'coffee' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_coffeemaker", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_12_cup_programmable",
            contains_any(fa, ["12-cup", "12 cup"]) and contains_any(fa, ["programmable"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.check("answer_stainless_4plus_rating",
            contains_all(fa, ["stainless"]) and (any(contains_any(fa, [c[2]]) for c in matched) if matched else False),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
