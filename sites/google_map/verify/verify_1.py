#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--1.

Tell me one bus stop that is nearest to the intersection of main street and Amherst street in Altavista.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The bus stop located at the Main St & Amherst St intersection in Altavista, VA is
    'Altavista Transit Stop #14' (place new-york alias altavista-va-main-st-amherst-st-bus-stop),
    address 'Main St & Amherst St, Altavista, VA 24501', description 'Public bus stop
    located at Main St & Amherst St. Serves local Altavista and Lynchburg Transit routes.'
    The other Altavista stops sit at other corners (Main & 7th, Bedford Ave, Main & 1st,
    Amherst & Bedford, Main & Pittsylvania, Broad & Amherst, 9th & Amherst, Town Transit Center).
    Source: /search?q=bus+stops+in+altavista (9 results) + the stop's place page.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Altavista bus-stop search or the stop's place page | answer
  identifies Altavista Transit Stop #14 with Main & Amherst evidence | read-
  only DB
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
    j = Judge('Google Map--1', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_altavista_bus_stops", navigated_to(t, "altavista"),
            "altavista search or place page in the trajectory")
    j.check("answer_main_amherst_stop",
            contains_any(fa, ["altavista transit stop #14", "altavista transit stop 14",
                              "transit stop #14", "transit stop no. 14"]),
            f"final={fa[:200]!r}")
    j.check("answer_intersection_evidence", contains_all(fa, ["main", "amherst"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
