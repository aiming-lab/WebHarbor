#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--12.

Find 5 places that serve burgers near 44012 zip code and sort these 5 places by highest rating.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's burger search near 44012 (Avon Lake, OH) returns 14 places:
    Avon Lake Burger Bar 4.8, Pickle Bill's Lobster House 4.7, Lake Erie Burger
    House 4.7, Five Guys Avon Lake 4.6, Bubba's 33 4.5, Walnut Grove Burgers 4.5,
    Smashburger Avon Lake 4.4, Shoreline Grill & Burger Co. 4.4, Red Robin Avon
    Lake 4.3, Wendy's Avon Lake 4.2, Marina Fries & Shakes 4.2, Burger King - Avon
    Lake 4.1, Pier 22 Burger Bar 4.0, Classic Burger Co. 3.8. The highest-rated is
    Avon Lake Burger Bar (4.8).
    Source: /search?q=burgers+near+44012&sort=rating (14 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a burger search near 44012 | answer lists five result places including
  the top-rated Avon Lake Burger Bar, presented in non-increasing rating order
  | read-only DB
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
    j = Judge('Google Map--12', a.no_llm)
    t, fa = grade_common(j, a)
    RATING_TABLE = {
        "Avon Lake Burger Bar": 4.8, "Pickle Bill's Lobster House": 4.7,
        "Lake Erie Burger House": 4.7, "Five Guys Avon Lake": 4.6,
        "Bubba's 33": 4.5, "Walnut Grove Burgers": 4.5, "Smashburger Avon Lake": 4.4,
        "Shoreline Grill & Burger Co.": 4.4, "Red Robin Avon Lake": 4.3,
        "Wendy's Avon Lake": 4.2, "Marina Fries & Shakes": 4.2,
        "Burger King - Avon Lake": 4.1, "Pier 22 Burger Bar": 4.0,
        "Classic Burger Co.": 3.8,
    }
    j.check("nav_burger_search", navigated_to(t, "burger"),
            "burger search near 44012 in the trajectory")
    j.check("answer_lists_five_places",
            count_names(fa, list(RATING_TABLE)) >= 5,
            f"matched={count_names(fa, list(RATING_TABLE))} final={fa[:200]!r}")
    j.check("answer_includes_top_rated", name_in(fa, "Avon Lake Burger Bar"),
            f"final={fa[:200]!r}")
    j.check("answer_sorted_by_rating_desc", rating_order_ok(fa, RATING_TABLE),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
