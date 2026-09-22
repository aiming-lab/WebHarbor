#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--33.

Search for a portable air conditioner on Amazon suitable for a room size of 300 sq ft, with energy efficiency rating, and compare the prices of the top three search results.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Exactly three portable ACs cover 300 sq ft and carry an energy rating:
    BLACK+DECKER BPACT08WT 8000 BTU, CEER 7.0, $329.99; Midea 10000 BTU, CEER
    8.0, $389.00; Honeywell MN10CESWW 10000 BTU, CEER 7.8, $409.99. The
    comparison must cover all three prices (LG covers 250 sq ft, SereneLife
    325, Whynter 500).

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
    j = Judge('Amazon--33', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_portable_ac_search",
            navigated_to(t, "portable") or navigated_to(t, "air conditioner") or navigated_to(t, "air+conditioner"),
            f"urls={[u for u in urls if 'portable' in u.lower() or 'conditioner' in u.lower()][:4]}")
    j.check("nav_300_sqft_scoping",
            search_url_with(t, ["300"])
            or visited_product(t, "black-decker-bpact08wt-8000-btu-portable-ac-300-sq-ft")
            or visited_product(t, "midea-10000-btu-portable-ac-300-sq-ft")
            or visited_product(t, "honeywell-mn10cesww-portable-ac-10000-btu-300-sq-ft"),
            "300-sq-ft scoped search or one of the three product pages")
    j.check("answer_all_three_models",
            contains_any(fa, ["black+decker", "black & decker", "black and decker", "black decker", "bpact08wt"])
            and contains_all(fa, ["midea"]) and contains_all(fa, ["honeywell"]),
            f"final={fa[:260]!r}")
    j.check("answer_three_prices_compared",
            price_in(fa, 329.99) and price_in(fa, 389.00) and price_in(fa, 409.99),
            f"final={fa[:260]!r}")
    j.check("answer_energy_rating",
            contains_any(fa, ["ceer", "energy rating", "energy efficiency", "7.0", "8.0", "7.8"]),
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
