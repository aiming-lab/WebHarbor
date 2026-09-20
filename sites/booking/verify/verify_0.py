#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--0.

Find a Mexico hotel with deals for December 25-26 (a deal = an on-page discount
badge or Genius deal; those labels exist only on the property detail page).

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Mexico City properties carrying a deal: Polanco Boutique Hotel (25% off,
    Genius, $162 struck through to $122) and St. Regis Mexico City (20% off,
    $261 struck through to $209). The other four Mexico City properties carry
    no deal on the mirror.

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
    "Polanco Boutique Hotel": [
        "Polanco Boutique Hotel",
        "polanco",
        "polanco boutique"
    ],
    "St. Regis Mexico City": [
        "St. Regis Mexico City",
        "st regis mexico city",
        "st. regis mexico"
    ]
}

PROPERTY_SLUGS = ["polanco-boutique-hotel-mexico-city", "st-regis-mexico-city-mexico-city"]


def main():
    a = parse_args()
    j = Judge('Booking--0', a.no_llm)
    t, fa = grade_common(j, a)
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("nav_mexico_search", search_url_with(t, ["q=mexico"]) or navigated_to(t, "/city/"),
            "a /search?q=... mexico results page (or city page)")
    j.check("nav_deal_property_page",
            visited_property(t, "polanco-boutique-hotel-mexico-city")
            or visited_property(t, "st-regis-mexico-city-mexico-city")
            or navigated_to(t, "stays?city=mexico-city") or navigated_to(t, "/stays?city=mexico-city")
            or navigated_to(t, "/city/mexico-city"),
            "deal evidence exists on the property page (GENIUS/-25%/-20% badges), on the"
            " /stays?city=mexico-city cards (GENIUS badge + $162->$122 strikethrough) and on"
            " the /city/mexico-city cards (GENIUS badge); the plain search page shows none")
    j.check("answer_names_deal_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {list(ALLOWED)}")
    j.check("answer_states_the_deal",
            contains_any(fa, ["%", "genius", "discount", "deal", " off "]),
            f"final={fa[:200]!r} the answer must convey the deal (percent off / genius / discount)")
    j.emit()


if __name__ == "__main__":
    main()
