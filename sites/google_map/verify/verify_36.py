#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--36.

Identify 5 restaurants serving pizza near the 30309 zip code and rank them by their ratings.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's pizza search near 30309 (Atlanta) returns 11 places:
    Antico Pizza Napoletana 4.8 (0.1 mi), Varasano's Pizzeria 4.7 (0.1 mi),
    Junior's Pizza Midtown 4.7 (0.2 mi), Ammazza Midtown 4.6 (0.2 mi), Tony's
    Family Pizzeria 4.6 (0.3 mi), Fellini's Pizza Midtown 4.5 (0.2 mi), Fellini's
    Pizza Atlanta 4.5 (1.8 mi), Midtown Pizza Kitchen 4.5 (0.1 mi), Double Zero
    Atlanta 4.4 (0.0 mi), Grant Central Pizza 4.3 (0.2 mi), Pizza Hut Midtown
    Atlanta 3.8 (0.3 mi). The highest-rated is Antico Pizza Napoletana (4.8).
    Source: /search?q=pizza+near+30309&sort=rating (11 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a pizza search near 30309 | answer lists five result restaurants
  including the top-rated Antico Pizza Napoletana, ranked in non-increasing
  rating order | read-only DB
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
    j = Judge('Google Map--36', a.no_llm)
    t, fa = grade_common(j, a)
    RATING_TABLE = {
        "Antico Pizza Napoletana": 4.8, "Varasano's Pizzeria": 4.7,
        "Junior's Pizza Midtown": 4.7, "Ammazza Midtown": 4.6,
        "Tony's Family Pizzeria": 4.6, "Fellini's Pizza Midtown": 4.5,
        "Fellini's Pizza Atlanta": 4.5, "Midtown Pizza Kitchen": 4.5,
        "Double Zero Atlanta": 4.4, "Grant Central Pizza": 4.3,
        "Pizza Hut Midtown Atlanta": 3.8,
    }
    j.check("nav_pizza_search", navigated_to(t, "pizza"),
            "pizza search near 30309 in the trajectory")
    j.check("answer_lists_five_pizza_places",
            count_names(fa, list(RATING_TABLE)) >= 5,
            f"matched={count_names(fa, list(RATING_TABLE))} final={fa[:200]!r}")
    j.check("answer_includes_top_rated", name_in(fa, "Antico Pizza Napoletana"),
            f"final={fa[:200]!r}")
    j.check("answer_ranked_by_rating_desc", rating_order_ok(fa, RATING_TABLE),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
