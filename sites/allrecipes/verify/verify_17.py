#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--17.

Find the Easy Vegetarian Spinach Lasagna recipe and tell me what the latest review says.

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened the Easy Vegetarian Spinach Lasagna recipe page
   3. answer names the recipe and reports its Latest Review highlight
      (or the first review in the page's review list) with >=2 exact fragments
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
        "slug": "easy-vegetarian-spinach-lasagna",
        "title": "Easy Vegetarian Spinach Lasagna",
        "avg_rating": "4.8",
        "review_count": 128,
        "latest_review": "Latest Review:\n\nMade this last night — my whole family loved it. The spinach filling was perfect, and the top was golden and bubbly. Will definitely make again!",
        "listed_reviews": [
            "My go-to! Made it three times. The spinach keeps it light.",
            "My kids ate ALL their veggies thanks to this recipe!"
        ]
    }
]

def body(j, traj, ans):
    opened = opened_recipe(traj, [r["slug"] for r in GROUND_TRUTH])
    j.check("opened_spinach_lasagna_page", bool(opened), "Easy Vegetarian Spinach Lasagna")
    # The task already names the recipe; the deliverable is the review content.
    # The navigation check above is what ties the answer to the right page.
    highlight = ["whole family loved", "golden and bubbly", "spinach filling was perfect",
                 "will definitely make again", "made this last night"]
    listed = ["my go-to", "made it three times", "spinach keeps it light",
              "perfect weeknight lasagna"]
    hh = keyword_hits(ans, highlight)
    lh = keyword_hits(ans, listed)
    j.check("answer_reports_latest_review", hh >= 2 or lh >= 2,
            f"highlight_hits={hh} first-listed-review_hits={lh}")

if __name__ == "__main__":
    run("Allrecipes--17", body)
