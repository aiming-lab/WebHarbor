#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--6.

Find all Uniqlo locations in Chicago, IL.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Uniqlo search returns six locations: Uniqlo Michigan Avenue
    (830 N Michigan Ave, Chicago, IL 60611), Uniqlo State Street (40 S State St,
    Chicago, IL 60603), Uniqlo Woodfield Mall (5 Woodfield Mall, Schaumburg, IL 60173),
    Uniqlo Oakbrook Center (100 Oakbrook Center, Oak Brook, IL 60523),
    Uniqlo Lincoln Park (2526 N Clark St, Chicago, IL 60614), Uniqlo Wicker Park
    (1569 N Milwaukee Ave, Chicago, IL 60622). Four carry Chicago, IL addresses;
    Woodfield Mall and Oakbrook Center are suburban (Schaumburg / Oak Brook).
    Source: /search?q=uniqlo (6 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Uniqlo search or Uniqlo place pages | answer names ALL FOUR Chicago-
  address Uniqlo locations (suburban malls optional) | read-only DB
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
    j = Judge('Google Map--6', a.no_llm)
    t, fa = grade_common(j, a)
    CHICAGO_UNIQLO = ["Uniqlo Michigan Avenue", "Uniqlo State Street",
                      "Uniqlo Lincoln Park", "Uniqlo Wicker Park"]
    j.check("nav_uniqlo_search", navigated_to(t, "uniqlo"),
            "uniqlo search URL or Uniqlo place page in the trajectory")
    j.check("answer_names_chicago_uniqlos",
            count_names(fa, CHICAGO_UNIQLO) == len(CHICAGO_UNIQLO),
            f"matched={count_names(fa, CHICAGO_UNIQLO)}/4 final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
