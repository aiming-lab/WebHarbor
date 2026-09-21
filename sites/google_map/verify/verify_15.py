#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--15.

Find daytime only parking nearest to Madison Square Garden. Summarize what people are saying about it.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The nearest daytime-only parking to Madison Square Garden is 'Chelsea Parking
    on 30th' (place alias new-york-ny-chelsea-day-only-lot, 285 W 34th St, New
    York, NY 10001, 0.1 mi from MSG), hours 'Mon-Fri: 7:00 AM - 6:00 PM, Closed
    Sat-Sun' (daytime only, closed weekends), described as an outdoor lot near
    8th Avenue popular with MSG event attendees. Its three visible reviews say:
    (5 stars) 'Great parking right next to MSG. Safe and clean.'; (5 stars) 'Easy
    in and out, helpful staff at Chelsea Day-Only Lot.'; (2 stars) 'Pricey on
    event nights but very convenient.'
    Source: /search?q=parking+near+madison+square+garden&sort=distance + the lot's place page.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an MSG parking search or the daytime lot's page | answer identifies
  Chelsea Parking on 30th and summarizes its reviews (safe/clean, easy in-out,
  helpful staff, pricey on event nights but convenient) | read-only DB
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
    j = Judge('Google Map--15', a.no_llm)
    t, fa = grade_common(j, a)
    REVIEW_TOKENS = ["safe", "clean", "easy in and out", "helpful staff", "pricey",
                     "convenient", "event night", "right next to msg", "late-night"]
    j.check("nav_msg_parking_search",
            navigated_any(t, ["madison square garden", "msg"]) or visited_place(t, "new-york-ny-chelsea-day-only-lot"),
            "MSG parking search or the Chelsea day-only lot page in the trajectory")
    j.check("answer_identifies_chelsea_day_only_lot",
            contains_any(fa, ["chelsea parking on 30th", "chelsea day-only lot", "chelsea day only lot"]),
            f"final={fa[:200]!r}")
    matched_reviews = sum(1 for tok in REVIEW_TOKENS if contains_any(fa, [tok]))
    j.check("answer_summarizes_reviews", matched_reviews >= 3,
            f"matched={matched_reviews} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
