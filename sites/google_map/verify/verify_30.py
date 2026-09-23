#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--30.

Locate a parking lot near the Brooklyn Bridge that open 24 hours. Review the user comments about it.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The 24-hour parking lot nearest the Brooklyn Bridge is 'Brooklyn Bridge
    Waterfront Garage' (55 Old Fulton St, Brooklyn, NY 11201, 0.2 mi from the
    bridge, 'Open 24 hours', '24-hour covered garage at the Brooklyn Bridge
    waterfront'). Its three visible reviews: (5 stars) 'Open 24 hours, very
    convenient for late-night visits to Brooklyn Bridge.'; (4 stars) 'Clean and
    safe with friendly staff. A bit pricey but worth it.'; (5 stars) 'Best
    parking option near the bridge - always has space.' The other 24h lot, Jay
    Street Garage (1.0 mi), has no reviews on its page.
    Source: /search?q=parking+near+brooklyn+bridge&hours=24h + the garage's place page.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Brooklyn Bridge parking search or the garage's page | answer names
  Brooklyn Bridge Waterfront Garage, its 24-hour status, and summarizes its
  user reviews | read-only DB
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
    j = Judge('Google Map--30', a.no_llm)
    t, fa = grade_common(j, a)
    REVIEW_TOKENS = ["late-night", "open 24 hours", "clean", "safe", "friendly staff",
                     "pricey", "always has space", "best parking option", "convenient"]
    j.check("nav_brooklyn_bridge_parking",
            navigated_to(t, "brooklyn bridge") or visited_place(t, "brooklyn-ny-brooklyn-bridge-24h-parking"),
            "brooklyn bridge parking search or the garage page in the trajectory")
    j.check("answer_names_waterfront_garage",
            name_in(fa, "Brooklyn Bridge Waterfront Garage"),
            f"final={fa[:200]!r}")
    j.check("answer_24h_evidence", contains_any(fa, ["24"]),
            f"final={fa[:200]!r}")
    matched = sum(1 for tok in REVIEW_TOKENS if contains_any(fa, [tok]))
    j.check("answer_summarizes_reviews", matched >= 2,
            f"matched={matched} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
