#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--22.

Find a Best Buy store near zip code 33139.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The Best Buy search near 33139 (Miami Beach) returns six stores; the one
    actually near the zip is 'Best Buy Miami Beach' (1205 Washington Ave, Miami
    Beach, FL 33139, 4.2 stars, 0.2 mi from the zip centroid). The others are
    8-14 miles away (Aventura 11.3, Doral 9.9, Coral Gables 8.7, Dadeland 13.1,
    Kendall-Pinecrest 14.1).
    Source: /search?q=best+buy+near+33139 (6 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Best Buy search near 33139 or the store's page | answer names Best
  Buy Miami Beach | read-only DB
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
    j = Judge('Google Map--22', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_best_buy_search",
            navigated_phrase(t, "best buy") or visited_place(t, "miami-beach-fl-best-buy-miami-beach"),
            "best buy search or the Miami Beach store page in the trajectory")
    j.check("answer_best_buy_miami_beach",
            contains_all(fa, ["best buy", "miami beach"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
