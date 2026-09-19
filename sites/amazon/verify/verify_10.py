#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--10.

Find the cost of a 2-year protection for PS4 on Amazon.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    '2-Year Protection Plan for PS4 ($250-$300)' by Asurion costs $24.99
    (the 3-Year plan at $34.99 is the distractor).

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
    j = Judge('Amazon--10', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_protection_plan",
            navigated_to(t, "ps4") or navigated_to(t, "protection")
            or visited_product(t, "2-year-protection-plan-for-ps4-250-300"),
            f"urls={[u for u in urls if 'protection' in u.lower() or 'ps4' in u.lower()][:4]}")
    j.check("answer_two_year_ps4",
            contains_all(fa, ["ps4"]) and contains_any(fa, ["2-year", "2 year", "two-year", "two year"]),
            f"final={fa[:200]!r}")
    j.check("answer_cost_24_99", price_in(fa, 24.99), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
