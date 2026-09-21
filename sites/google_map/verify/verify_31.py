#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--31.

First search New York's Central Park Zoo on Google Map, and then find the way to share the map. What is the generated sharing link?

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The Central Park Zoo place page (new-york-ny-central-park-zoo, 64 W 5th Ave,
    4.4 stars, 9,420 reviews) carries a 'Share this place' box with the
    generated sharing link 'http://localhost:40008/place/new-york-ny-central-park-zoo'
    (shown both in the readonly share-URL input and as the share-url text).
    Source: /place/new-york-ny-central-park-zoo, Share box.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Central Park Zoo place page | answer reports the generated sharing
  link pointing at the Central Park Zoo place URL on localhost | read-only DB
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
    j = Judge('Google Map--31', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_central_park_zoo_page",
            visited_place(t, "new-york-ny-central-park-zoo") or navigated_phrase(t, "central park zoo"),
            "central park zoo place page or search in the trajectory")
    j.check("answer_sharing_link",
            contains_all(fa, ["localhost", "new-york-ny-central-park-zoo"]),
            f"final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
