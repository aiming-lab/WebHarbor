#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--8.

Find the cheapest Samsung-made Android tablet with screen between 10-10.9 inches on Amazon. Only answer the cheapest one.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Samsung tablets with 10-10.9in screens: Galaxy Tab A7 10.4in $189.99,
    Galaxy Tab S6 Lite 10.4in $349.99, Galaxy Tab S9 FE 10.9in $449.99. The
    A9+ (11.0in), A8 (8.7in), S8 (11.0in), S7 FE (12.4in) fall outside the
    window. Cheapest = Samsung Galaxy Tab A7 at $189.99.

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
    j = Judge('Amazon--8', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_samsung_tablet", navigated_to(t, "samsung") or navigated_to(t, "tab"),
            f"urls={[u for u in urls if 'tab' in u.lower() or 'samsung' in u.lower()][:4]}")
    j.check("nav_screen_evidence",
            visited_product(t, "samsung-galaxy-tab-a7-10-4-32gb")
            or visited_product(t, "samsung-galaxy-tab-s6-lite-10-4-64gb")
            or visited_product(t, "samsung-galaxy-tab-s9-fe-10-9-128gb"),
            "a 10-10.9in tablet's product page opened (screen sizes live on the "
            "detail page, not on cards - required to verify the size window)")
    j.check("answer_tab_a7", contains_all(fa, ["tab a7"]), f"final={fa[:200]!r}")
    j.check("answer_price_189_99", price_in(fa, 189.99), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
