#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--38.

Find a bird feeder on Amazon suitable for small birds, with an anti-squirrel mechanism, and check if it's available with free shipping.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Small-bird anti-squirrel feeders: Squirrel Buster Plus $78.95 (free
    shipping), Perky-Pet Squirrel-Be-Gone Max $43.99 (free shipping), Gray
    Bunny Small Bird Feeder $29.99 (free shipping), Stokes Select Squirrel-X
    $34.99 (delivery fee applies — NOT free shipping). The Droll Yankees and
    Woodlink caged feeders are for medium birds. The answer's shipping status
    must match the feeder it names.

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
    j = Judge('Amazon--38', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("squirrel buster", 78.95, True), ("perky-pet", 43.99, True),
             ("perky pet", 43.99, True), ("gray bunny", 29.99, True),
             ("stokes", 34.99, False)]
    j.check("nav_bird_feeder_search", navigated_to(t, "feeder") or navigated_to(t, "bird"),
            f"urls={[u for u in urls if 'feeder' in u.lower() or 'bird' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_feeder", bool(matched),
            f"matched={sorted({c[0] for c in matched})} of {sorted({c[0] for c in CANDS})}")
    j.check("answer_anti_squirrel_small_birds",
            contains_any(fa, ["squirrel"]) and contains_any(
                fa, ["small bird", "small birds", "songbird", "songbirds", "small songbird"]),
            f"final={fa[:200]!r}")
    frees = [c for c in matched if c[2]]
    fees = [c for c in matched if not c[2]]
    if fees and not frees:
        j.check("answer_shipping_status",
                contains_any(fa, ["not free", "no free", "fee applies", "shipping fee",
                                  "standard shipping", "isn't free", "isn’t free", "does not include free"]),
                "Stokes Select is NOT free-shipping; the answer must say so")
    else:
        j.check("answer_shipping_status",
                contains_any(fa, ["free shipping", "free delivery", "free shipment"]),
                "the named feeder ships free; the answer must say so")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
