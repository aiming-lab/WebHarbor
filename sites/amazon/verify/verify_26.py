#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--26.

Search for a portable Bluetooth speaker on Amazon with a water-resistant design, under $50. It should have a minimum battery life of 10 hours.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Water-resistant portable bluetooth speakers under $50 with >=10h battery:
    OontZ Angle 3 $29.99 (14h), JBL Clip 4 $49.95 (10h), EarFun UBOOM Slim
    $42.99 (16h), Anker Soundcore 2 $39.99 (24h), Tribit StormBox Micro $44.99
    (12h). The JBL Go 3 (5h) and DOSS SoundBox (4h) fail the battery floor.

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
    j = Judge('Amazon--26', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("oontz", 29.99, ["14 hour", "14-hour", "14h", "14 h"]),
             ("jbl clip 4", 49.95, ["10 hour", "10-hour", "10h", "10 h"]),
             ("earfun", 42.99, ["16 hour", "16-hour", "16h", "16 h"]),
             ("soundcore 2", 39.99, ["24 hour", "24-hour", "24h", "24 h"]),
             ("stormbox", 44.99, ["12 hour", "12-hour", "12h", "12 h"])]
    j.check("nav_speaker_search", navigated_to(t, "speaker"),
            f"urls={[u for u in urls if 'speaker' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_speaker", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_water_resistant",
            contains_any(fa, ["water-resistant", "water resistant", "waterproof"]), f"final={fa[:200]!r}")
    j.check("answer_battery_10_hours_plus",
            any(contains_any(fa, c[2]) for c in matched) if matched else False,
            "the named speaker's >=10h battery life")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
