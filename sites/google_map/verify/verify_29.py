#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--29.

Identify bus stops in Ypsilanti, MI, list three of them.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The Ypsilanti bus-stop search returns seven Ypsilanti stops: Depot Town
    Bus Stop (0.6 mi), Cross St & Washington St Bus Stop (0.1 mi), Michigan Ave &
    Hamilton St Bus Stop (0.0 mi), Eastern Michigan University Bus Stop (0.3 mi),
    Washtenaw Ave & Huron St Bus Stop (0.2 mi), Pearl St & Adams St Bus Stop
    (0.3 mi), Ypsilanti Transit Center (0.2 mi). (Three Avon Lake places also
    match the query tokens at ~96 mi and are not Ypsilanti stops.)
    Source: /search?q=bus+stops+in+ypsilanti+mi (10 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Ypsilanti bus-stop search or a stop's page | answer lists at least
  three of the seven Ypsilanti bus stops | read-only DB
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
    j = Judge('Google Map--29', a.no_llm)
    t, fa = grade_common(j, a)
    YPSILANTI_STOPS = ["Depot Town Bus Stop", "Cross St & Washington St Bus Stop",
                      "Michigan Ave & Hamilton St Bus Stop",
                      "Eastern Michigan University Bus Stop",
                      "Washtenaw Ave & Huron St Bus Stop", "Pearl St & Adams St Bus Stop",
                      "Ypsilanti Transit Center"]
    j.check("nav_ypsilanti_search", navigated_to(t, "ypsilanti"),
            "ypsilanti search URL or place page in the trajectory")
    j.check("answer_lists_three_stops", count_names(fa, YPSILANTI_STOPS) >= 3,
            f"matched={count_names(fa, YPSILANTI_STOPS)} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
