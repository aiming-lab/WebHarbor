#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--10.

Search for a park in the state of California called Castle Mountains National Monument and find out it's Basic Information.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The Castle Mountains National Monument place page shows: 4.7 stars (320
    reviews), 'National Monument in Mojave, CA', address Barnwell, CA 92364,
    Open 24 hours, phone +1 (760) 252-6100, website www.nps.gov/camo, About:
    'Castle Mountains National Monument is a United States national monument
    located in eastern San Bernardino County, California, within the Mojave Desert.
    Established in 2016, it protects grasslands, Joshua trees, and the historic
    Hart townsite.' Amenities: Hiking, Scenic views, Wildlife viewing, No facilities.
    Source: /place/castle-mountains-ca-castle-mountains-national-monument.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the Castle Mountains National Monument page or its search | answer
  reports the basic information: national monument + 2016 establishment + at
  least one further on-page fact | read-only DB
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
    j = Judge('Google Map--10', a.no_llm)
    t, fa = grade_common(j, a)
    EXTRA_FACTS = ["mojave", "joshua", "hart", "san bernardino", "barnwell",
                  "92364", "hiking", "scenic views", "wildlife", "no facilities",
                  "open 24", "92364"]
    j.check("nav_castle_mountains",
            visited_place(t, "castle-mountains-ca-castle-mountains-national-monument")
            or navigated_phrase(t, "castle mountains"),
            "castle mountains place page or search in the trajectory")
    j.check("answer_national_monument_and_2016",
            contains_all(fa, ["national monument"]) and contains_any(fa, ["2016"]),
            f"final={fa[:200]!r}")
    j.check("answer_further_basic_info",
            sum(1 for tok in EXTRA_FACTS if tok in fa.lower()) >= 1,
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
