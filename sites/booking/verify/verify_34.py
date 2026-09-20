#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--34.

Search for a hotel in Berlin for a three-night stay March 15-18 2024 for one
adult; tell the price in USD and CNY for the three-night stay.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Any Berlin hotel is acceptable; the property pages show the USD per-night
    price plus a CNY conversion line (rate 7.2). The answer must name the hotel
    and give USD + CNY figures consistent with that hotel's on-page prices
    (per night or for the three nights).

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
    "The Charming by Curt Suites": [
        "The Charming by Curt Suites"
    ],
    "Locke at East Side Gallery": [
        "Locke at East Side Gallery"
    ],
    "sly Berlin": [
        "sly Berlin"
    ],
    "Boutique Hotel Château Royal": [
        "Boutique Hotel Chateau Royal",
        "Boutique Hotel Château Royal"
    ],
    "Wilmina Hotel": [
        "Wilmina Hotel"
    ],
    "Wilde Aparthotels Berlin, Checkpoint Charlie": [
        "Wilde Aparthotels Berlin, Checkpoint Charlie"
    ],
    "KPM Hotel &amp; Residences Berlin, a Member of Design Hotels": [
        "KPM Hotel & Residences Berlin, a Member of Design Hotels",
        "KPM Hotel and Residences Berlin, a Member of Design Hotels"
    ],
    "Hotel Indigo Berlin - East Side Gallery": [
        "Hotel Indigo Berlin - East Side Gallery"
    ],
    "ADELANTE Boutique Hotel": [
        "ADELANTE Boutique Hotel"
    ],
    "Casa Camper Berlin": [
        "Casa Camper Berlin"
    ]
}
SLUGS = ["the-charming-by-curt-suites-berlin", "locke-at-east-side-gallery-berlin", "sly-berlin-berlin", "boutique-hotel-château-royal-berlin", "wilmina-hotel-berlin", "wilde-aparthotels-berlin-checkpoint-charlie-berlin", "kpm-hotel-amp-residences-berlin-a-member-of-design-hotels-berlin", "hotel-indigo-berlin-east-side-gallery-berlin", "adelante-boutique-hotel-berlin", "casa-camper-berlin-berlin"]
USD = {
    "The Charming by Curt Suites": [
        77,
        77.35,
        91.0,
        231,
        232.04999999999998,
        273.0
    ],
    "Locke at East Side Gallery": [
        85.0,
        255.0
    ],
    "sly Berlin": [
        100.0,
        300.0
    ],
    "Boutique Hotel Château Royal": [
        134.0,
        402.0
    ],
    "Wilmina Hotel": [
        104,
        104.3,
        149.0,
        312,
        312.9,
        447.0
    ],
    "Wilde Aparthotels Berlin, Checkpoint Charlie": [
        250,
        250.5,
        334.0,
        750,
        751.5,
        1002.0
    ],
    "KPM Hotel &amp; Residences Berlin, a Member of Design Hotels": [
        228.75,
        229,
        305.0,
        686.25,
        687,
        915.0
    ],
    "Hotel Indigo Berlin - East Side Gallery": [
        204.0,
        272.0,
        612.0,
        816.0
    ],
    "ADELANTE Boutique Hotel": [
        330.0,
        990.0
    ],
    "Casa Camper Berlin": [
        79.0,
        237.0
    ]
}
CNY = {
    "The Charming by Curt Suites": [
        556.92,
        557,
        655,
        655.2,
        1670.7599999999998,
        1671,
        1965,
        1965.6000000000001
    ],
    "Locke at East Side Gallery": [
        612,
        1836
    ],
    "sly Berlin": [
        720,
        2160
    ],
    "Boutique Hotel Château Royal": [
        964.8000000000001,
        965,
        2894.4,
        2895
    ],
    "Wilmina Hotel": [
        750.96,
        751,
        1072.8,
        1073,
        2252.88,
        2253,
        3218.3999999999996,
        3219
    ],
    "Wilde Aparthotels Berlin, Checkpoint Charlie": [
        1803.6000000000001,
        1804,
        2404.8,
        2405,
        5410.8,
        5412,
        7214.400000000001,
        7215
    ],
    "KPM Hotel &amp; Residences Berlin, a Member of Design Hotels": [
        1647,
        2196,
        4941,
        6588
    ],
    "Hotel Indigo Berlin - East Side Gallery": [
        1468.8,
        1469,
        1958,
        1958.4,
        4406.4,
        4407,
        5874,
        5875.200000000001
    ],
    "ADELANTE Boutique Hotel": [
        2376,
        7128
    ],
    "Casa Camper Berlin": [
        568.8000000000001,
        569,
        1706.4,
        1707
    ]
}


def main():
    a = parse_args()
    j = Judge('Booking--34', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_berlin",
            search_url_with(t, ["q=berlin"]) or any(visited_property(t, s) for s in SLUGS),
            "the Berlin results page or a Berlin property page (CNY line renders on property pages)")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_berlin_hotel", bool(named),
            f"final={fa[:200]!r} expected a Berlin hotel by name")
    if not named:
        j.check("answer_usd_cny", False, "no named property")
        j.emit()
    import re as _re
    nums = [float(x.replace(",", "")) for x in _re.findall(r"\d[\d,]*\.?\d*", fa)]
    usd_ok = any(any(abs(n - u) <= 1.01 for u in USD[named]) for n in nums)
    cny_ok = any(any(abs(n - c) <= 4 for c in CNY[named]) for n in nums)
    j.check("answer_usd_price", usd_ok,
            f"final={fa[:300]!r} accepted USD for {named!r}={USD[named]}")
    j.check("answer_cny_price", cny_ok,
            f"final={fa[:300]!r} accepted CNY for {named!r}={CNY[named]}")
    j.emit()


if __name__ == "__main__":
    main()
