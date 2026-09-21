#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--24.

Browse for a compact air fryer on Amazon with a capacity of 2 to 3 quarts. It should have a digital display, auto shutoff and be priced under $100.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Compact 2-3 quart digital air fryers with auto shutoff under $100: Dash
    Compact 2qt $44.99, Instant Vortex 2qt $49.95, COSORI Premium 2.1qt $69.99,
    Chefman TurboFry 3qt $54.99, Ninja AF101 2qt $79.99, PowerXL 3qt $79.99.
    The GoWISE 2qt is analog (no digital display).

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
    j = Judge('Amazon--24', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("dash", 44.99, ["2 quart", "2-quart", "2 qt", "2qt"]),
             ("instant vortex", 49.95, ["2 quart", "2-quart", "2 qt", "2qt"]),
             ("cosori", 69.99, ["2.1 quart", "2.1-quart", "2.1 qt", "2.1qt"]),
             ("chefman", 54.99, ["3 quart", "3-quart", "3 qt", "3qt"]),
             ("ninja af101", 79.99, ["2 quart", "2-quart", "2 qt", "2qt"]),
             ("powerxl", 79.99, ["3 quart", "3-quart", "3 qt", "3qt"])]
    j.check("nav_air_fryer_search", navigated_to(t, "fryer"),
            f"urls={[u for u in urls if 'fryer' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_fryer", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_capacity_2_to_3_quarts",
            any(contains_any(fa, c[2]) for c in matched) if matched else False,
            "the named fryer's 2-3 quart capacity")
    j.check("answer_digital_auto_shutoff",
            contains_any(fa, ["digital"]) and contains_any(fa, ["auto shutoff", "auto-shutoff", "shutoff", "shut-off", "shut off"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
