#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--11.

Find a stainless steel kitchen sink with double bowls on Amazon. Sort the results and find the cheapest one with FREE delivery.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Every stainless kitchen sink in the catalog is spec'd 'Double Bowl 50/50'.
    Sorted by price the FREE-delivery ones start at Kindred KSD30DL Double Bowl
    Drop-In Sink $189.99 (Ruvati $279.00, Elkay $249.99, Kraus Standart PRO
    $399.95 charge a delivery fee; MR Direct 3322S $219.00 also ships free but
    is not the cheapest). Cheapest with FREE delivery = Kindred $189.99.

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
    j = Judge('Amazon--11', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_kitchen_sink", navigated_to(t, "sink"),
            f"urls={[u for u in urls if 'sink' in u.lower()][:4]}")
    j.check("nav_price_sort_or_product",
            search_url_with(t, ["sort=price"]) or visited_product(t, "kindred-ksd30dl-double-bowl-drop-in-sink"),
            "price sort or the Kindred product page")
    j.check("answer_kindred", contains_all(fa, ["kindred"]), f"final={fa[:200]!r}")
    j.check("answer_price_189_99", price_in(fa, 189.99), f"final={fa[:200]!r}")
    j.check("answer_free_delivery",
            contains_any(fa, ["free delivery", "free shipping", "free shipment"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
