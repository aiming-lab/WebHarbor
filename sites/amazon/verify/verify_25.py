#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--25.

Search for a queen-sized, hypoallergenic mattress topper on Amazon. It should have a memory foam material and be priced between $50 to $100.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Queen hypoallergenic memory-foam toppers $50-$100: LINENSPA 2-inch Gel
    Memory Foam Topper - Queen $59.99 (4.6) and Subrtex 2-inch Memory Foam
    Topper - Queen $64.99 (4.6). TEMPUR-Topper Supreme is $379, Sleep
    Innovations lacks the hypoallergenic tag, ViscoSoft/LUCID are latex
    blends, Zinus lacks the tag.

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
    j = Judge('Amazon--25', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("linenspa", 59.99), ("subrtex", 64.99)]
    j.check("nav_topper_search", navigated_to(t, "topper"),
            f"urls={[u for u in urls if 'topper' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_topper", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_queen_sized", contains_all(fa, ["queen"]), f"final={fa[:200]!r}")
    j.check("answer_memory_foam_hypoallergenic",
            contains_all(fa, ["memory foam"]) and contains_all(fa, ["hypoallergenic"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
