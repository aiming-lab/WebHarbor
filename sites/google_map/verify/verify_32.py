#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--32.

Search for plumbers available now but not open 24 hours in Orlando, FL.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Orlando plumbers that are available now but NOT open 24 hours (per the
    mirror's open-now filter and their hours): Orlando Plumbing Solutions
    (Mon-Sat 8:00 AM - 8:00 PM), Central Florida Plumbers (Mon-Sun 7:00 AM -
    9:00 PM), Mr. Rooter Plumbing Orlando (Mon-Sun 7:00 AM - 10:00 PM).
    The 24-hour plumbers - All Hours Plumbing Orlando and Roto-Rooter Orlando -
    do NOT qualify; I-4 Plumbing Services and Benjamin Franklin Plumbing Orlando
    are not currently open and do not qualify either.
    Source: /search?q=plumbers+orlando&hours=open_now (5 results) + place pages.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Orlando plumber search or a plumber's page | answer lists at least
  two of the three available-now non-24h plumbers | read-only DB
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
    j = Judge('Google Map--32', a.no_llm)
    t, fa = grade_common(j, a)
    QUALIFYING = ["Orlando Plumbing Solutions", "Central Florida Plumbers",
                 "Mr. Rooter Plumbing Orlando"]
    PLUMB_SLUGS = ["orlando-fl-orlando-plumbing-solutions", "orlando-fl-central-florida-plumbers",
                   "orlando-fl-mr-rooter-plumbing-orlando"]
    j.check("nav_orlando_plumbers",
            navigated_to(t, "plumber") or visited_any_place(t, PLUMB_SLUGS),
            "orlando plumber search or plumber page in the trajectory")
    j.check("answer_two_plus_qualifying", count_names(fa, QUALIFYING) >= 2,
            f"matched={count_names(fa, QUALIFYING)} final={fa[:200]!r}")
    j.check("answer_available_now_not_24h",
            contains_any(fa, ["open now", "currently open", "not open 24", "not 24-hour",
                              "not 24 hours", "not 24h", "excluding", "excludes"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
