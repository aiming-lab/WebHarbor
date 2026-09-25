#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--23.

Determine the shortest walking route from The Metropolitan Museum of Art to Times Square in New York.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Walking directions from The Metropolitan Museum of Art (1000 5th Ave) to
    Times Square (Manhattan, NY 10036) offer three alternatives: via Main St
    1.8 mi ~36 min, via Park Ave 2.0 mi ~41 min, via Broadway 2.4 mi ~47 min.
    The shortest walking route is via Main St: 1.8 miles, about 36 minutes.
    Source: /directions?from=The+Metropolitan+Museum+of+Art&to=Times+Square&mode=walking.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: walking directions The Met -> Times Square | answer identifies the
  shortest route via Main St with 1.8 mi and 36 min | read-only DB
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
    j = Judge('Google Map--23', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_met_times_square_walking",
            navigated_to(t, "mode=walking") and navigated_to(t, "metropolitan")
            and navigated_phrase(t, "times square"),
            "walking directions URL from the Met to Times Square in the trajectory")
    j.check("answer_shortest_route_main_st", contains_any(fa, ["main st"]),
            f"final={fa[:200]!r}")
    j.check("answer_distance_1_8_mi", distance_claim(fa, 1.8), f"final={fa[:200]!r}")
    j.check("answer_duration_36_min", minutes_claim(fa, 36), f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
