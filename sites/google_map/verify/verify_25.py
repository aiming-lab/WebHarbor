#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--25.

Search for a parking facility near the Fox Theater in Detroit that closes at night.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; re-enumerated from every
candidate facility's own place page during the acceptance rework; the catalog
is fixed by the seed DB and carries no wall-clock content):
    Parking facilities near the Fox Theatre (distance pills from the anchored
    'parking near Fox Theatre Detroit' search) whose own pages show hours that
    close at night (all of them qualify and all are accepted):
      Broadway Lot            (1331 Broadway St,  0.1 mi, Mon-Sun 6AM-11PM)
      Fox Theatre Garage      (2100 Woodward Ave, 0.3 mi, Mon-Sun 7:00 AM - 12:00 AM)
      Detroit Athletic Club Lot (2180 Woodward Ave, 0.4 mi, Mon-Sun 8:00 AM - 10:00 PM)
      Comerica Park Lot       (2100 Witherell St, 0.6 mi, Mon-Sun 6:00 AM - 11:00 PM)
      Cass Park Lot           (2701 Cass Ave,    0.7 mi, Mon-Sun 8AM-12AM)
      Woodward Avenue Lot     (2140 Woodward Ave, 0.7 mi, Mon-Sun 6:00 AM - 10:00 PM)
      Grand Circus Parking    (2160 Woodward Ave, 0.9 mi, Mon-Sun 7:00 AM - 11:00 PM)
    Facilities that are open 24 hours per their own pages and therefore do NOT
    qualify: Grand Circus Deck (0.0 mi), the overnight 'Comerica Park Lot'
    facility (/place/detroit-mi-comerica-park-overnight-lot, 0.1 mi), Foxtown
    Garage (0.2 mi), Premium Garage Downtown (0.7 mi). Note the display-name
    collision: 'Comerica Park Lot' names both a qualifying facility (Witherell
    St, 6:00 AM - 11:00 PM) and a 24-hour facility; the name is accepted because
    the qualifying facility is a correct answer, and the night-closing evidence
    check below still rejects answers that report 24-hour operation.
    Source: /search?q=parking+near+Fox+Theatre+Detroit&sort=distance +
    /place/detroit-mi-fox-theatre-detroit?nearby_category=parking + each lot's
    place page.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Fox Theatre parking search or any qualifying lot's page | answer
  names one of the qualifying facilities | answer carries night-closing
  evidence (a PM closing hour, midnight / 12:00 AM, or an explicit
  closes-at-night phrase — word-boundary regex, so 'open 24 hours' or
  'never closes' cannot satisfy it) | read-only DB
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
    j = Judge('Google Map--25', a.no_llm)
    t, fa = grade_common(j, a)
    LOTS = ["Broadway Lot", "Fox Theatre Garage", "Detroit Athletic Club Lot",
            "Comerica Park Lot", "Cass Park Lot", "Woodward Avenue Lot",
            "Grand Circus Parking"]
    LOT_SLUGS = ["detroit-mi-broadway-day-lot", "detroit-mi-fox-theatre-garage",
                 "detroit-mi-detroit-athletic-club-lot", "detroit-mi-comerica-park-lot",
                 "detroit-mi-cass-park-evening-lot", "detroit-mi-woodward-ave-night-lot",
                 "detroit-mi-grand-circus-parking"]
    j.check("nav_fox_theatre_parking",
            navigated_phrase(t, "fox theater") or navigated_phrase(t, "fox theatre")
        or visited_any_place(t, LOT_SLUGS),
            "fox theatre parking search or a qualifying lot page in the trajectory")
    j.check("answer_names_closing_lot", count_names(fa, LOTS) >= 1,
            f"matched={count_names(fa, LOTS)} final={fa[:200]!r}")
    j.check("answer_closes_at_night_evidence",
            re_any(fa, [r"\d{1,2}(:\d{2})?\s*pm\b", r"\bmidnight\b",
                        r"\b12(:00)?\s*am\b", r"closes\s+at\s+night",
                        r"closed\s+at\s+night", r"not\s+open\s+24",
                        r"not\s+24\s+hours?"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
