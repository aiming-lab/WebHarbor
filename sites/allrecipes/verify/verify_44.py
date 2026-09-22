#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--44.

List at least 6 holiday recipes sections mentioned in the Occasions section of Allrecipes.

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened /occasions
   3. answer lists >=6 holiday/occasion sections shown on the page
Input/Output: see verify_lib.run / Judge.emit.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run, opened_recipe, opened_page, mentions_title,
                        mentions_number, mentions_time, keyword_hit, keyword_hits,
                        mentions_any, nutrition_hits)

# Ground truth frozen from the mirror's own pages (rating/review counts, info
# bar times, ingredient and direction text as rendered on the recipe pages).
GROUND_TRUTH = [
    {
        "page": "/occasions",
        "occasions": [
            "Christmas",
            "Thanksgiving",
            "Easter",
            "Hanukkah",
            "Valentine's Day",
            "Fourth of July",
            "Halloween",
            "New Year's Eve",
            "Mother's Day",
            "Father's Day"
        ]
    }
]

def body(j, traj, ans):
    j.check("opened_occasions_section", opened_page(traj, "/occasions"),
            "task requires the Allrecipes Occasions section")
    hits = [o for o in GROUND_TRUTH[0]["occasions"] if keyword_hit(ans, o)]
    j.check("answer_lists_occasion_sections", len(hits) >= 6,
            f"matched_occasions={hits}")

if __name__ == "__main__":
    run("Allrecipes--44", body)
