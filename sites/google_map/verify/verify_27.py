#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--27.

Locate the Target stores in Atlanta, GA. How many results are shown on the map.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Target search for Atlanta returns six Target stores:
    Target Atlantic Station (375 18th St NW), Target Midtown Atlanta (375 W
    Peachtree St NW), Target Edgewood (1275 Caroline St NE), Target Lindbergh
    (2539 Piedmont Rd NE), Target Ponce City (650 Ponce De Leon Ave NE), Target
    Cumberland (2201 Cobb Pkwy SE). The search header reads '6 places found'.
    The verbatim query 'target stores in atlanta, ga' additionally surfaces
    three non-Target places (Whole Foods Market Midtown, Margaret Mitchell
    House, REI Co-op Atlanta), so 'how many results are shown' has two
    defensible readings on the mirror and the count check accepts either.
    Source: /search?q=target+atlanta (6 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Target Atlanta search | answer states the result count of the
  executed search (both on-mirror readings accepted; no store-name check —
  the task text asks only for the count) | read-only DB
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
    j = Judge('Google Map--27', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_target_search", navigated_to(t, "target"),
            "target atlanta search URL in the trajectory")
    j.check("answer_count_is_six_or_nine_results", 6 in numbers_in(fa) or 9 in numbers_in(fa),
            f"numbers={numbers_in(fa)[:12]} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
