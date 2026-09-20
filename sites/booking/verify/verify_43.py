#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--43.

Search for properties in Los Angeles, browse the results page filters, list
some of them.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The LA results page sidebar exposes: Sort results by (Our top picks, Best
    reviewed, Price lowest/highest first, Property rating (stars), Distance from
    city centre); Popular filters (Free cancellation, Breakfast included, Free
    WiFi, Swimming pool, Parking, Fitness center, Spa & wellness, Airport
    shuttle, Pet-friendly, Air conditioning, Bicycle rental); Property star
    rating (5+...1+ stars); Review score (Superb 9+, Very good 8+, Good 7+,
    Pleasant 6+); Brand (per-brand counts).

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

FILTER_TOKENS = ["free cancellation", "breakfast included", "free wifi", "swimming pool",
    "parking", "fitness center", "spa", "airport shuttle", "pet-friendly", "pet friendly",
    "air conditioning", "bicycle rental", "star rating", "stars", "review score",
    "brand", "sort", "best reviewed", "price", "distance from", "top picks"]


def main():
    a = parse_args()
    j = Judge('Booking--43', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_la_results", search_url_with(t, ["los angeles"]),
            "the Los Angeles results page (the filter sidebar renders there)")
    f = norm(fa)
    hits = sorted({tok for tok in FILTER_TOKENS if tok in f})
    j.check("answer_lists_filters", len(hits) >= 3,
            f"final={fa[:400]!r} filters mentioned={hits}")
    j.emit()


if __name__ == "__main__":
    main()
