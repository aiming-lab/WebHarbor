#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--1.

Find the cheapest available hotel room for a three night stay from Jan 1 in
Jakarta for 2 adults; answer the cheapest hotel room and the price.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Cheapest Jakarta property: RedDoorz Plus Menteng (Standard Double Room
    $66/night on the room table; $53/night discounted card price; 3-night totals
    $198 list / $159 discounted). Every other Jakarta property costs more at
    every room tier.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, contains_affirmative,
                        mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)

ALLOWED = {"RedDoorz Plus Menteng": ["RedDoorz Plus Menteng", "reddoorz plus", "reddoorz menteng", "reddoorz"]}
SLUG = "reddoorz-plus-menteng-jakarta"
PRICE_SET = [52.8, 53, 66, 158.4, 159, 198]


def main():
    a = parse_args()
    j = Judge('Booking--1', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_jakarta_search", search_url_with(t, ["q=jakarta"]) or visited_property(t, SLUG),
            "a Jakarta results page (all six cards render with prices; the cheapest is"
            " identifiable by comparing card prices) or the cheapest property page")
    j.check("answer_cheapest_hotel", contains_any(fa, ["reddoorz"]),
            f"final={fa[:200]!r}")
    j.check("answer_price", any(price_in(fa, p) for p in PRICE_SET),
            f"final={fa[:200]!r} accepted={PRICE_SET}")
    j.emit()


if __name__ == "__main__":
    main()
