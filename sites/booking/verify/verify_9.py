#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--9.

Find hotels for 2 adults in London under $250/night for four days from
December 25; the answer must offer at least 3 options.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    London properties at or under $250 per night (6 qualify):
    art'otel London Hoxton, room2 London Chiswick Hometel, The Londoner, Hart Shoreditch Hotel London, Curio Collection by Hilton, Pan Pacific London, nhow London.

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

ALLOWED = {
    "art'otel London Hoxton": [
        "art'otel London Hoxton"
    ],
    "room2 London Chiswick Hometel": [
        "room2 London Chiswick Hometel"
    ],
    "The Londoner": [
        "The Londoner"
    ],
    "Hart Shoreditch Hotel London, Curio Collection by Hilton": [
        "Hart Shoreditch Hotel London, Curio Collection by Hilton"
    ],
    "Pan Pacific London": [
        "Pan Pacific London"
    ],
    "nhow London": [
        "nhow London"
    ]
}
SLUGS = ["artotel-london-hoxton-london", "room2-london-chiswick-hometel-london", "the-londoner-london", "hart-shoreditch-hotel-london-curio-collection-by-hilton-london", "pan-pacific-london-london", "nhow-london-london"]


def main():
    a = parse_args()
    j = Judge('Booking--9', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_london_price_capped",
            search_url_with(t, ["london", "max_price=250"]) or search_url_with(t, ["london"])
            or sum(1 for s in SLUGS if visited_property(t, s)) >= 2,
            "London results (cards show per-night prices; the under-$250 set is enforced"
            " by the answer check) or at least two qualifying property pages")
    found = [nm for nm in ALLOWED if any(al.lower() in norm(fa) for al in ALLOWED[nm])]
    j.check("answer_offers_3_options", len(found) >= 3,
            f"final={fa[:300]!r} distinct qualifying options named={found}")
    j.emit()


if __name__ == "__main__":
    main()
