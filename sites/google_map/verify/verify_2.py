#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--2.

Find Apple Stores close to zip code 90028.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Apple Store search near zip 90028 (Hollywood) returns seven
    'Apple ...' stores with distance pills from the zip centroid:
    Apple The Grove (2.6 mi), Apple Beverly Center (3.5 mi), Apple Americana at Brand (5.0 mi),
    Apple Century City (5.8 mi), Apple Sherman Oaks (7.7 mi), Apple Pasadena (9.5 mi),
    Apple Third Street Promenade (11.6 mi).
    Source: /search?q=apple+store+near+90028 (8 results, incl. one non-Apple distractor).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Apple-store search or an Apple place page | answer names at least
  two of the seven Apple stores | read-only DB
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
    j = Judge('Google Map--2', a.no_llm)
    t, fa = grade_common(j, a)
    APPLE_STORES = ["Apple The Grove", "Apple Third Street Promenade", "Apple Century City",
                   "Apple Pasadena", "Apple Beverly Center", "Apple Americana at Brand",
                   "Apple Sherman Oaks"]
    APPLE_SLUGS = ["los-angeles-ca-apple-the-grove", "los-angeles-ca-apple-third-street-promenade",
                   "los-angeles-ca-apple-century-city", "los-angeles-ca-apple-pasadena",
                   "los-angeles-ca-apple-beverly-center", "los-angeles-ca-apple-americana-at-brand",
                   "los-angeles-ca-apple-sherman-oaks"]
    j.check("nav_apple_store_search", navigated_to(t, "apple") or visited_any_place(t, APPLE_SLUGS),
            "apple search URL or an Apple place page in the trajectory")
    j.check("answer_two_plus_apple_stores", count_names(fa, APPLE_STORES) >= 2,
            f"matched={count_names(fa, APPLE_STORES)} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
