#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--4.

Find the used Nintendo Switch Lite on Amazon then filter by 'Used - Good', tell me the cheapest one that is 'Used - Good'.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Used-Good Switch Lites: Yellow $159.99, Blue $164.99, Gray $149.99. The
    cheapest Used-Good unit is the Gray one at $149.99 (the $139.99 Blue unit is
    Used - Acceptable, a distractor).

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
    j = Judge('Amazon--4', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_switch_search", navigated_to(t, "switch"),
            f"urls={[u for u in urls if 'switch' in u.lower()][:4]}")
    j.check("nav_used_good_filter_or_product",
            search_url_with(t, ["condition=used"]) or visited_product(t, "nintendo-switch-lite-gray"),
            "condition=Used - Good filter or the Gray unit's page")
    j.check("answer_gray", contains_all(fa, ["gray"]), f"final={fa[:200]!r}")
    j.check("answer_used_good_condition",
            contains_any(fa, ["used - good", "used good"]), f"final={fa[:200]!r}")
    j.check("answer_price_149_99", price_in(fa, 149.99), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
