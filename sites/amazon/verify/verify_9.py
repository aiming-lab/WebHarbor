#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--9.

Find a dog bed on Amazon that is washable and has a length of at least 30 inches.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Washable dog beds with length >= 30in: Bedsure Large Dog Bed 32in $44.99,
    Bedsure XL Orthopedic Dog Bed 42in $69.99, Amazon Basics Pet Dog Bed Large
    34in $35.99. The MidWest 22in bed is washable but too short.

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
    j = Judge('Amazon--9', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("bedsure large", 44.99, "32"), ("bedsure xl", 69.99, "42"),
             ("amazon basics", 35.99, "34")]
    j.check("nav_dog_bed_search", navigated_to(t, "dog") or navigated_to(t, "bed"),
            f"urls={[u for u in urls if 'dog' in u.lower() or 'bed' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_all(fa, [c[0]])]
    j.check("answer_qualifying_bed", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_length_30_inches_or_more",
            any(contains_any(fa, [c[2] + '"', c[2] + ' inch', c[2] + '-inch', c[2] + ' inches',
                                  c[2] + '-in', c[2] + 'in']) for c in matched) if matched else False,
            "32in / 42in / 34in length quoted for the named bed")
    j.check("answer_washable", contains_all(fa, ["washable"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
