#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--5.

Search a hotel with free WiFi and air conditioning in Bali, Jan 1-4 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Bali properties with free WiFi AND air conditioning (7 qualify).

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
    "Grandmas Plus Hotel Airport": [
        "Grandmas Plus Hotel Airport"
    ],
    "Four Seasons Sayan": [
        "Four Seasons Sayan"
    ],
    "The Mulia Nusa Dua": [
        "The Mulia Nusa Dua"
    ],
    "COMO Uma Ubud": [
        "COMO Uma Ubud"
    ],
    "Hanging Gardens of Bali": [
        "Hanging Gardens of Bali"
    ],
    "AYANA Resort Bali": [
        "AYANA Resort Bali"
    ],
    "Padma Resort Legian": [
        "Padma Resort Legian"
    ]
}
SLUGS = ["grandmas-plus-hotel-airport-bali", "four-seasons-sayan-bali", "the-mulia-nusa-dua-bali", "como-uma-ubud-bali", "hanging-gardens-of-bali", "ayana-resort-bali", "padma-resort-legian"]


def main():
    a = parse_args()
    j = Judge('Booking--5', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_bali_wifi_ac",
            search_url_with(t, ["bali", "wifi=1"]) and search_url_with(t, ["air_conditioning=1"])
            or any(visited_property(t, s) for s in SLUGS),
            "Bali results with wifi+AC filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} Bali wifi+AC properties")
    j.check("answer_mentions_wifi_and_ac",
            contains_any(fa, ["wifi", "wi-fi"]) and contains_any(fa, ["air conditioning", "air-conditioning", " a c ", " ac "]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
