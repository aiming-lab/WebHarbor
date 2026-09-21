#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--0.

Find 5 beauty salons with ratings greater than 4.8 in Seattle, WA.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Exactly five Seattle beauty salons are rated strictly above 4.8 (all 4.9):
    Gene Juarez Salon & Spa (4.9, 2,310 reviews), Habitude Salon & Day Spa (4.9, 1,870),
    Sanctuary Salon & Med Spa (4.9, 1,420), Urbane Hair Salon (4.9, 1,200),
    Vain Seattle (4.9, 1,650). Le Salon Belleza is exactly 4.8 and does NOT satisfy
    'greater than 4.8'; every other Seattle salon in the search is 4.7 or below.
    Source: /search?q=beauty+salons+in+seattle+washington&min_rating=4.8 (6 results) and each salon's place page.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a salon search or a salon place page | answer names ALL FIVE qualifying
  salons with their 4.9-rating evidence | read-only DB
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
    j = Judge('Google Map--0', a.no_llm)
    t, fa = grade_common(j, a)
    QUALIFYING = ["Gene Juarez Salon & Spa", "Habitude Salon & Day Spa",
                   "Sanctuary Salon & Med Spa", "Urbane Hair Salon", "Vain Seattle"]
    SALON_SLUGS = ["seattle-wa-gene-juarez-salon-spa", "seattle-wa-habitude-salon-day-spa",
                   "seattle-wa-sanctuary-salon-med-spa", "seattle-wa-urbane-hair-salon",
                   "seattle-wa-le-salon-belleza", "seattle-wa-vain-seattle"]
    j.check("nav_salon_search", navigated_to(t, "salon") or visited_any_place(t, SALON_SLUGS),
            "salon search URL or a salon place page in the trajectory")
    j.check("answer_names_all_five_qualifying", count_names(fa, QUALIFYING) == len(QUALIFYING),
            f"matched={count_names(fa, QUALIFYING)}/5 final={fa[:200]!r}")
    j.check("answer_ratings_gt_4_8", contains_any(fa, ["4.9"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
