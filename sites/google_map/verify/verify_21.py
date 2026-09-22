#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--21.

Identify the nearest bus stop to the corner of Elm Street and Oak Street in Massachusetts.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Two Salem, MA bus stops sit at the Elm & Oak corner per the mirror:
    'Elm St & Oak St Bus Stop' (Elm St & Oak St, Salem, MA 01970, 'Public bus
    stop at Elm St & Oak St, Salem, MA 01970.') and 'Oak St & Elm St Stop'
    (Oak St & Elm St, Salem, MA 01970, 'MBTA bus stop with sheltered seating and
    route map.'). Both are the Elm/Oak corner stop; either identification is correct.
    The Elm St & Main St Bus Stop is in Cambridge and is NOT at the Elm/Oak corner.
    Source: /search?q=bus+stops+elm+street+oak+street+massachusetts + both place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an elm/oak bus-stop search or one of the two stops' pages | answer
  identifies a bus stop at Elm & Oak in Salem MA | read-only DB
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
    j = Judge('Google Map--21', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_elm_oak_search",
            navigated_to(t, "elm") or visited_any_place(
                t, ["salem-ma-elm-st-oak-st-bus-stop", "salem-ma-oak-st-elm-st-stop"]),
            "elm/oak bus stop search or place page in the trajectory")
    j.check("answer_elm_oak_corner_stop",
            contains_all(fa, ["elm", "oak"]) and contains_any(fa, ["bus stop", "transit stop"]),
            f"final={fa[:200]!r}")
    j.check("answer_salem_ma_evidence",
            contains_any(fa, ["salem", "elm st & oak st", "oak st & elm st"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
