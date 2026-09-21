#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--8.

Find a place to climb within 2 miles of zip code 90028.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Climbing facilities within 2 miles of the 90028 zip centroid:
    Hollywood Boulders (1107 N Bronson Ave, 0.1 mi), Beverly Hills Climbing Studio
    (0.2 mi), Hollywood Rock Climbing Wall (1845 N Vine St, 0.3 mi),
    Sunset Climbing Collective (1521 N Sunset Blvd, 0.4 mi), Stoney Point Rock Gym
    (1.5 mi), LA Boulders Melrose (1.5 mi). Vermont Bouldering Co. (2.1 mi) is
    outside the 2-mile radius, and Cliffs of Id / Stronghold / LA Boulders are 6.9+ mi.
    Source: /search?q=climbing+near+90028 (10 results with distance pills).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a climbing search anchored on 90028 or a qualifying gym's page | answer
  names one qualifying climbing place with distance evidence of 2 miles or
  less | read-only DB
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
    j = Judge('Google Map--8', a.no_llm)
    t, fa = grade_common(j, a)
    CLIMB6 = ["Hollywood Boulders", "Beverly Hills Climbing Studio",
             "Hollywood Rock Climbing Wall", "Sunset Climbing Collective",
             "Stoney Point Rock Gym", "LA Boulders Melrose"]
    CLIMB_SLUGS = ["los-angeles-ca-hollywood-boulders", "los-angeles-ca-beverly-hills-climbing-studio",
                   "los-angeles-ca-hollywood-rock-climbing-wall", "los-angeles-ca-sunset-climbing-collective",
                   "los-angeles-ca-stoney-point-rock-gym", "los-angeles-ca-la-boulders-melrose"]
    j.check("nav_climbing_search",
            navigated_any(t, ["climb", "bouldering", "90028"]) or visited_any_place(t, CLIMB_SLUGS),
            "climbing search near 90028 or a qualifying gym page in the trajectory")
    j.check("answer_names_qualifying_climb", count_names(fa, CLIMB6) >= 1,
            f"matched={count_names(fa, CLIMB6)} final={fa[:200]!r}")
    mi_vals = extract_mi_values(fa)
    j.check("answer_within_2_miles",
            any(v <= 2.0 for v in mi_vals)
            or contains_any(fa, ["within 2 miles", "within 2 mi", "within two miles",
                                 "under 2 miles", "less than 2 miles", "2 miles or less"]),
            f"mi_values={mi_vals} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
