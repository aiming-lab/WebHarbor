#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--29.

Find a set of solar-powered garden lights on Amazon with a minimum pack of 10 lights. They should be LED and priced under $50.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    LED solar garden light packs with >=10 lights under $50: BEAU JARDIN
    10-pack $29.99, OSORD 12-pack $34.99, GIGALUMI 16-pack $39.99, Solpex
    24-pack $43.99. Moonrays and Hampton Bay are 8-packs.

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
    j = Judge('Amazon--29', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("beau jardin", 29.99, "10"), ("osord", 34.99, "12"),
             ("gigalumi", 39.99, "16"), ("solpex", 43.99, "24")]
    j.check("nav_solar_search", navigated_to(t, "solar"),
            f"urls={[u for u in urls if 'solar' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_pack", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_pack_10_plus_lights",
            any(contains_any(fa, [c[2] + "-pack", c[2] + " pack", "pack of " + c[2]])
                or count_claim(fa, c[2], "light")
                for c in matched) if matched else False,
            "the named pack's 10+ light count")
    j.check("answer_led_solar",
            contains_all(fa, ["led"]) and contains_all(fa, ["solar"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
