#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--31.

Find a compact digital camera on Amazon with a zoom capability of at least 10x, rated 4 stars or higher, and priced between $100 to $300.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Compact digital cameras >=10x zoom, >=4 stars, $100-$300: Canon PowerShot
    ELPH 360 HS 12x $249.99 (4.5), Canon PowerShot SX620 HS 25x $259.99 (4.5),
    Nikon COOLPIX A1000 35x $279.99 (4.6), Canon PowerShot SX740 HS 40x $279.00
    (4.7), Panasonic LUMIX ZS80D 30x $299.99 (4.6). Sony W830 (8x) and Kodak
    FZ55 (5x) fail the zoom floor.

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
    j = Judge('Amazon--31', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("elph 360", 249.99, "12x"), ("sx620", 259.99, "25x"),
             ("coolpix a1000", 279.99, "35x"), ("sx740", 279.00, "40x"),
             ("zs80d", 299.99, "30x")]
    j.check("nav_camera_search", navigated_to(t, "camera"),
            f"urls={[u for u in urls if 'camera' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_camera", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_zoom_10x_plus",
            any(contains_any(fa, [c[2]]) for c in matched) if matched else False,
            "the named camera's >=10x zoom")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.check("answer_rating_4_plus",
            contains_any(fa, ["4.5", "4.6", "4.7", "4 star", "4+"]) if matched else False,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
