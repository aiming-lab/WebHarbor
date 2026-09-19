#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--3.

Find climbing gears and sort the results by price high to low. Answer the first 3 results after sorting.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Search 'climbing gear' returns 10 products; price high-to-low the first
    three are: Mammut 9.5 Crag Classic Climbing Rope 60m $219.95, Evolv Shaman
    Climbing Shoes $179.00, Petzl GriGri Plus Belay Device $149.95 (no price
    ties among the top three).

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
    j = Judge('Amazon--3', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_climbing_search", navigated_to(t, "climbing"),
            f"urls={[u for u in urls if 'climbing' in u.lower()][:4]}")
    m_i = first_mention(fa, ["mammut"])
    e_i = first_mention(fa, ["evolv", "shaman"])
    p_i = first_mention(fa, ["grigri", "gri gri", "petzl"])
    j.check("answer_all_three_named", None not in (m_i, e_i, p_i),
            f"first mentions mammut@{m_i} evolv@{e_i} petzl@{p_i}")
    j.check("answer_sorted_high_to_low", None not in (m_i, e_i, p_i) and m_i < e_i < p_i,
            "Mammut $219.95 -> Evolv $179.00 -> Petzl $149.95 order in the answer")
    j.check("answer_three_prices",
            price_in(fa, 219.95) and price_in(fa, 179.00) and price_in(fa, 149.95),
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
