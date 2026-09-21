#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--37.

Locate a queen-sized bedspread on Amazon with a floral pattern, and check if it's available in blue color.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Queen floral bedspreads available in blue: Bedsure Queen Bedspread $49.99,
    Mellanni Queen Bedspread $59.99, HIG Queen Bedspread Coverlet $64.99,
    Oakland Living Queen Bedspread $89.99, Madison Park Queen Bedspread $104.99
    (each lists Blue among its colors). Pinzon's floral bedspread comes only in
    Rose/Pink/Ivory/Gray; the Chic Home floral bedspread is King-sized.

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
    j = Judge('Amazon--37', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("oakland living", 89.99), ("madison park", 104.99), ("mellanni", 59.99),
             ("hig queen", 64.99), ("hig bedspread", 64.99), ("hig coverlet", 64.99),
             ("bedsure", 49.99)]
    j.check("nav_bedspread_search", navigated_to(t, "bedspread"),
            f"urls={[u for u in urls if 'bedspread' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_bedspread", bool(matched),
            f"matched={sorted({c[0] for c in matched})} of {sorted({c[0] for c in CANDS})}")
    j.check("answer_floral_pattern", contains_all(fa, ["floral"]), f"final={fa[:200]!r}")
    j.check("answer_blue_available",
            contains_any(fa, ["blue"]) and contains_any(fa, ["available", "yes", "comes in", "offered"]),
            f"final={fa[:200]!r}")
    j.check("answer_queen_sized", contains_all(fa, ["queen"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
