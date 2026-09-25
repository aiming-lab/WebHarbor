#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--17.

Search for locksmiths open now but not open 24 hours in Texas City.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Texas City locksmiths that are open now but NOT open 24 hours (per the
    mirror's open-now filter and their hours): Texas City Locksmith Services
    (1200 Palmer Hwy, Mon-Sat 8:00 AM - 8:00 PM), Mainland Locksmiths (1320 Palmer
    Hwy, Mon-Sun 9:00 AM - 9:00 PM), Gulf Coast Lock & Key (1240 Palmer Hwy,
    Mon-Sun 7:00 AM - 10:00 PM). The 24-hour locksmiths - All Hours Locksmith
    Texas City and Texas Locks 24/7 - do NOT qualify. Bayshore Locksmith is not
    currently open and does not qualify either.
    Source: /search?q=locksmiths+in+texas+city&hours=open_now (5 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Texas City locksmith search or a locksmith's page | answer lists at
  least two of the three open-now non-24h locksmiths | read-only DB
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
    j = Judge('Google Map--17', a.no_llm)
    t, fa = grade_common(j, a)
    QUALIFYING = ["Texas City Locksmith Services", "Mainland Locksmiths", "Gulf Coast Lock & Key"]
    LOCK_SLUGS = ["texas-city-tx-texas-city-locksmith-services", "texas-city-tx-mainland-locksmiths",
                  "texas-city-tx-gulf-coast-lock-key"]
    j.check("nav_texas_city_locksmiths",
            navigated_to(t, "locksmith") or visited_any_place(t, LOCK_SLUGS),
            "texas city locksmith search or locksmith page in the trajectory")
    j.check("answer_two_plus_qualifying", count_names(fa, QUALIFYING) >= 2,
            f"matched={count_names(fa, QUALIFYING)} final={fa[:200]!r}")
    j.check("answer_open_now_not_24h",
            contains_any(fa, ["open now", "currently open", "not open 24", "not 24-hour",
                              "not 24 hours", "not 24h", "excluding", "excludes"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
