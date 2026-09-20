#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--35.

Search for a natural reserve in Texas called Big Bend National Park and gather its Basic Information.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The Big Bend National Park place page shows: 4.9 stars (6,800 reviews),
    'National Park in Big Bend, TX', address 1 Panther Junction, Big Bend
    National Park, TX 79834, Open 24 hours, phone +1 (432) 477-2251, website
    www.nps.gov/bibe, About: 'Big Bend National Park is a United States national
    park in West Texas, bordering Mexico. It encompasses more than 801,000 acres
    of the Chihuahuan Desert along the Rio Grande... Known for its diverse
    wildlife, mountain hiking, and river rafting.' Amenities: Camping, Hiking,
    River rafting, Visitor center, Stargazing.
    Source: /place/big-bend-tx-big-bend-national-park.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Big Bend National Park page or its search | answer reports the
  basic information: national park + at least two further on-page facts |
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
    j = Judge('Google Map--35', a.no_llm)
    t, fa = grade_common(j, a)
    FACTS = ["west texas", "801,000", "801000", "chihuahuan", "rio grande", "mexico",
             "hiking", "rafting", "stargazing", "camping", "visitor center", "open 24"]
    j.check("nav_big_bend",
            visited_place(t, "big-bend-tx-big-bend-national-park") or navigated_to(t, "big bend"),
            "big bend national park page or search in the trajectory")
    j.check("answer_national_park", contains_all(fa, ["national park"]),
            f"final={fa[:200]!r}")
    matched = sum(1 for tok in FACTS if contains_any(fa, [tok]))
    j.check("answer_basic_information_facts", matched >= 2,
            f"matched={matched} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
