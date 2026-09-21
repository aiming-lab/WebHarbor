#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--23.

Look for a men's waterproof digital sports watch with a heart rate monitor on Amazon. It should be priced between $50 to $100.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Waterproof digital sports watches with heart-rate monitor, $50-$100:
    Timex Men's Ironman Classic 30 $54.99 (4.7), Samsung Galaxy Fit 3 $59.99
    (4.5), Casio G-Shock DW5600 $64.99 (4.8), Fitbit Inspire 3 $79.95 (4.6),
    Suunto Core $89.99 (4.5), Garmin Forerunner 45 $99.99 (4.7).

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
    j = Judge('Amazon--23', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("ironman", 54.99), ("galaxy fit 3", 59.99), ("g-shock", 64.99),
             ("inspire 3", 79.95), ("suunto core", 89.99), ("forerunner 45", 99.99)]
    j.check("nav_watch_search", navigated_to(t, "watch"),
            f"urls={[u for u in urls if 'watch' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_watch", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_heart_rate_monitor",
            contains_any(fa, ["heart rate", "heart-rate", "heart rate monitor"]), f"final={fa[:200]!r}")
    j.check("answer_waterproof_digital",
            contains_any(fa, ["waterproof"]) and contains_any(fa, ["digital"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
