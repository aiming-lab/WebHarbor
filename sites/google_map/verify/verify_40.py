#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--40.

Find a restaurant in Boston that eats Boston lobster and asks for a rating of 4.6 or higher, and check out what a one-star review says.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Boston lobster restaurants rated 4.6 or higher (per the mirror's rating
    filter): Yvonne's Boston Lobster (4.6, 1,840 reviews, 'Seafood Restaurant in
    Boston, MA'), Neptune Oyster (4.8, 4,320), Pauli's North End (4.8, 2,210),
    Union Oyster House (4.7, 5,220), James Hook & Co. (4.7, 3,210), Legal Sea
    Foods - Long Wharf (4.6, 6,100). Each page carries a one-star review of the
    same shape: 'Very disappointing visit to <restaurant>. Lobster was overcooked
    and rubbery, the service was slow, and it was way overpriced for what we
    received. Would not recommend.'
    Source: /search?q=lobster+restaurant+boston&min_rating=4.6 (6 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a lobster-restaurant search with the rating constraint or a qualifying
  restaurant's page | answer names a qualifying restaurant and
  quotes/summarizes its one-star review | read-only DB
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, navigated_to, navigated_any, navigated_phrase,
                        visited_place, visited_any_place, name_in, count_names,
                        contains_all, contains_any, distance_claim, minutes_claim,
                        number_claim, rating_order_ok, extract_mi_values, numbers_in)

def main():
    a = parse_args()
    j = Judge('Google Map--40', a.no_llm)
    t, fa = grade_common(j, a)
    RESTAURANTS = ["Yvonne's Boston Lobster", "Neptune Oyster", "Pauli's North End",
                 "Union Oyster House", "James Hook & Co.", "Legal Sea Foods - Long Wharf"]
    RESTAURANT_SLUGS = ["boston-ma-yvonne-s-boston-lobster", "boston-ma-neptune-oyster",
                        "boston-ma-pauli-s-north-end", "boston-ma-union-oyster-house",
                        "boston-ma-james-hook-co", "boston-ma-legal-sea-foods-long-wharf"]
    ONE_STAR_TOKENS = ["overcooked", "rubbery", "slow", "overpriced",
                   "would not recommend", "disappointing"]
    j.check("nav_lobster_search",
            navigated_to(t, "lobster") or visited_any_place(t, RESTAURANT_SLUGS),
            "lobster restaurant search or a qualifying restaurant page in the trajectory")
    j.check("answer_names_qualifying_restaurant", count_names(fa, RESTAURANTS) >= 1,
            f"matched={count_names(fa, RESTAURANTS)} final={fa[:200]!r}")
    j.check("answer_one_star_review",
            contains_any(fa, ["1-star", "one-star", "1 star", "one star"]),
            f"final={fa[:200]!r}")
    matched = sum(1 for tok in ONE_STAR_TOKENS if contains_any(fa, [tok]))
    j.check("answer_one_star_content", matched >= 2,
            f"matched={matched} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
