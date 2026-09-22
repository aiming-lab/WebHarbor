#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--11.

Locate a large store in Washington that has kids' and maternity products, also check if it has a parking lot.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Washington-state stores carrying BOTH kids' and maternity products per their
    mirror pages: IKEA Renton ('Full kids' department, baby section, maternity
    carried seasonally. Ample free on-site parking.'), buybuy BABY Bellevue
    ('Dedicated baby and maternity specialty store... Free parking.'), Target
    Northgate Seattle ('Kids', baby, and maternity sections... parking garage
    connected via skybridge.'), Walmart Supercenter Renton, Motherhood Maternity
    Tukwila ('maternity wear... newborn / kids' apparel... shared mall parking').
    Every one of them shows a parking facility on its page. Bellevue Baby & Kids
    does not mention maternity products and is not accepted.
    Source: /search?q=kids+maternity (13 results) + the stores' place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a kids/maternity/baby store search or a qualifying store's page |
  answer names one qualifying Washington store and confirms its parking
  facility | read-only DB
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
    j = Judge('Google Map--11', a.no_llm)
    t, fa = grade_common(j, a)
    STORES = ["IKEA Renton", "buybuy BABY Bellevue", "Target Northgate Seattle",
               "Walmart Supercenter Renton", "Motherhood Maternity Tukwila"]
    STORE_SLUGS = ["ikea-renton", "buy-buy-baby-bellevue", "seattle-wa-target-northgate-seattle",
                   "seattle-wa-walmart-supercenter-renton", "seattle-wa-motherhood-maternity-tukwila"]
    j.check("nav_store_search",
            navigated_any(t, ["maternity", "kids"]) or navigated_phrase(t, "baby store")
        or visited_any_place(t, STORE_SLUGS),
            "kids/maternity store search or a qualifying store page in the trajectory")
    j.check("answer_names_qualifying_store", count_names(fa, STORES) >= 1,
            f"matched={count_names(fa, STORES)} final={fa[:200]!r}")
    j.check("answer_parking_lot_evidence",
            contains_any(fa, ["parking lot", "free parking", "on-site parking",
                              "parking garage", "ample parking", "shared mall parking",
                              "parking available"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
