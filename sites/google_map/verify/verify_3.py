#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--3.

The least amount of walking from Central Park Zoo to the Broadway Theater in New York.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Walking directions from Central Park Zoo (64 W 5th Ave) to the Broadway
    Theatre (1681 Broadway) offer three alternatives: via Main St 0.7 mi ~14 min,
    via Park Ave 0.8 mi ~15 min, via Broadway 0.9 mi ~18 min.
    The least-walking route is via Main St: 0.7 miles, about 14 minutes.
    The bare endpoint 'Broadway Theater' is ambiguous (8 matches) and the picker
    must be resolved to 'Broadway Theatre' (Entertainment, 1681 Broadway).
    Source: /directions?from=Central+Park+Zoo&to=Broadway+Theatre&mode=walking.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: walking directions Central Park Zoo -> Broadway Theatre | answer
  identifies the least-walking route via Main St with 0.7 mi and 14 min |
  read-only DB
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
    j = Judge('Google Map--3', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_walking_directions",
            navigated_to(t, "mode=walking") and navigated_phrase(t, "central park zoo")
            and navigated_to(t, "broadway"),
            "walking directions URL from Central Park Zoo to Broadway in the trajectory")
    j.check("answer_least_walking_route", contains_any(fa, ["main st"]),
            f"final={fa[:200]!r}")
    j.check("answer_distance_0_7_mi", distance_claim(fa, 0.7), f"final={fa[:200]!r}")
    j.check("answer_duration_14_min", minutes_claim(fa, 14), f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
