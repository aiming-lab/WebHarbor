#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--35.

Search for a natural reserve in Texas called Big Bend National Park and gather its Basic Information.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; re-verified during the
acceptance rework; the catalog is fixed by the seed DB and carries no
wall-clock content):
    The Big Bend National Park place page shows: 4.9 stars (6,800 reviews),
    'National Park in Big Bend, TX', address 1 Panther Junction, Big Bend
    National Park, TX 79834, Open 24 hours, phone +1 (432) 477-2251, website
    www.nps.gov/bibe, About: 'Big Bend National Park is a United States national
    park in West Texas, bordering Mexico. It encompasses more than 801,000 acres
    of the Chihuahuan Desert along the Rio Grande... Known for its diverse
    wildlife, mountain hiking, and river rafting.' Amenities: Camping, Hiking,
    River rafting, Visitor center, Stargazing, Trails & Walks.
    Source: /place/big-bend-tx-big-bend-national-park.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Big Bend National Park page or its search | answer reports the
  national park and its region as the page states it (word-boundary phrase
  'West Texas'; an answer placing the park in East Texas or near the Gulf of
  Mexico contradicts the page and FAILs) | at least two further on-page basic
  information facts with word-boundary matching (acreage, desert, river,
  amenities, hours, address, phone, website, rating) | read-only DB
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, navigated_to, navigated_any, navigated_phrase,
                        visited_place, visited_any_place, name_in, count_names,
                        contains_all, contains_any, distance_claim, minutes_claim,
                        number_claim, rating_order_ok, extract_mi_values, numbers_in,
                        re_any, re_count)

def main():
    a = parse_args()
    j = Judge('Google Map--35', a.no_llm)
    t, fa = grade_common(j, a)
    # Region: the page states 'in West Texas, bordering Mexico'. The region
    # claim is checked as a word-boundary phrase so an 'East Texas' answer can
    # never satisfy it, and a contradiction guard rejects the wrong-region
    # family (East Texas / Gulf of Mexico) outright.
    j.check("nav_big_bend",
            visited_place(t, "big-bend-tx-big-bend-national-park") or navigated_to(t, "big bend"),
            "big bend national park page or search in the trajectory")
    j.check("answer_national_park", contains_all(fa, ["national park"]),
            f"final={fa[:200]!r}")
    j.check("answer_region_west_texas",
            re_any(fa, [r"\bwest\s+texas\b"]),
            f"final={fa[:250]!r}")
    j.check("answer_region_consistent",
            not re_any(fa, [r"\beast\s+texas\b", r"\bgulf\s+of\s+mexico\b"]),
            f"final={fa[:250]!r}")
    # Further basic-information facts from the page, word-boundary anchored.
    FACTS = [r"\b801,000\b", r"\b801000\b", r"\bchihuahuan\b", r"\brio\s+grande\b",
             r"\bbordering\s+mexico\b", r"\bhiking\b", r"\briver\s+rafting\b",
             r"\brafting\b", r"\bstargazing\b", r"\bcamping\b",
             r"\bvisitor\s+center\b", r"\bopen\s+24\b", r"\btrails\b",
             r"\bpanther\s+junction\b", r"\b79834\b", r"\b477-2251\b",
             r"\bnps\.gov\b", r"\b4\.9\b", r"\b6,800\b", r"\b6800\b"]
    matched = re_count(fa, FACTS)
    j.check("answer_basic_information_facts", matched >= 2,
            f"matched={matched} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
