#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--40.

Choose a Shenzhen hotel, select March 6-8 2024, search, and report how much
it costs converted to Chinese Yuan on the page.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The search results and property pages show a CNY conversion (rate 7.2);
    selecting currency CNY shows per-card CNY prices. The answer must name the
    hotel and give its CNY figure as rendered on the page (per night, or the
    two-night total for March 6-8).

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)

ALLOWED = {
    "The St. Regis Shenzhen": [
        "The St. Regis Shenzhen"
    ],
    "Four Seasons Shenzhen": [
        "Four Seasons Shenzhen"
    ],
    "Grand Hyatt Shenzhen": [
        "Grand Hyatt Shenzhen"
    ],
    "Hilton Shenzhen Shekou": [
        "Hilton Shenzhen Shekou"
    ],
    "CitiGO Shenzhen": [
        "CitiGO Shenzhen"
    ]
}
SLUGS = ["the-st-regis-shenzhen-shenzhen", "four-seasons-shenzhen-shenzhen", "grand-hyatt-shenzhen-shenzhen", "hilton-shenzhen-shekou-shenzhen", "citigo-shenzhen-shenzhen"]
CNY = {
    "The St. Regis Shenzhen": [
        2044.8,
        2045,
        4089.6,
        4090
    ],
    "Four Seasons Shenzhen": [
        1857.6000000000001,
        1858,
        3715.2000000000003,
        3716
    ],
    "Grand Hyatt Shenzhen": [
        1821.6000000000001,
        1822,
        3643.2000000000003,
        3644
    ],
    "Hilton Shenzhen Shekou": [
        1095,
        1095.12,
        2190,
        2190.24
    ],
    "CitiGO Shenzhen": [
        612,
        1224
    ]
}


def main():
    a = parse_args()
    j = Judge('Booking--40', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_shenzhen",
            search_url_with(t, ["shenzhen"]) or any(visited_property(t, s) for s in SLUGS),
            "the Shenzhen results (currency selector / CNY conversion) or a property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_hotel", bool(named),
            f"final={fa[:200]!r} expected a Shenzhen hotel by name")
    if not named:
        j.emit()
    import re as _re
    nums = [float(x.replace(",", "")) for x in _re.findall(r"\d[\d,]*\.?\d*", fa)]
    cny_ok = any(any(abs(n - c) <= 4 for c in CNY[named]) for n in nums)
    j.check("answer_cny_price", cny_ok,
            f"final={fa[:300]!r} accepted CNY for {named!r}={CNY[named]}")
    j.emit()


if __name__ == "__main__":
    main()
