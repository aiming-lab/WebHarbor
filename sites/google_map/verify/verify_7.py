#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--7.

Find bus stops in Alanson, MI.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Alanson bus-stop search returns five stops:
    US-31 & Burr Ave Bus Stop (0.3 mi), Main St & River St Bus Stop (0.2 mi),
    Alanson Post Office Bus Stop (0.4 mi), Alanson Village Hall Stop (0.3 mi),
    US-31 & Crooked Lake Stop (0.5 mi).
    Source: /search?q=bus+stops+in+alanson+mi (5 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Alanson bus-stop search or a stop's place page | answer lists at
  least three of the five Alanson bus stops | read-only DB
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
    j = Judge('Google Map--7', a.no_llm)
    t, fa = grade_common(j, a)
    ALANSON_STOPS = ["US-31 & Burr Ave Bus Stop", "Main St & River St Bus Stop",
                     "Alanson Post Office Bus Stop", "Alanson Village Hall Stop",
                     "US-31 & Crooked Lake Stop"]
    j.check("nav_alanson_bus_stops", navigated_to(t, "alanson"),
            "alanson search URL or place page in the trajectory")
    j.check("answer_lists_three_plus_stops", count_names(fa, ALANSON_STOPS) >= 3,
            f"matched={count_names(fa, ALANSON_STOPS)} final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
