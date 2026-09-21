#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--36.

american apple pie >=4 stars >50 reviews + max temperature in Directions

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened a /recipe/<slug> page from the qualifying set
   3. the answer names the qualifying recipe it opened
   4. the answer states the recipe's on-page facts required by the task
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
        "slug": "classic-american-apple-pie",
        "title": "Classic American Apple Pie",
        "avg_rating": "4.4",
        "review_count": 121,
        "max_oven_temp": 425
    },
    {
        "slug": "grandma-s-apple-pie",
        "title": "Grandma's Apple Pie",
        "avg_rating": "4.3",
        "review_count": 99,
        "max_oven_temp": 400
    },
    {
        "slug": "old-fashioned-apple-pie",
        "title": "Old-Fashioned Apple Pie",
        "avg_rating": "4.4",
        "review_count": 111,
        "max_oven_temp": 425
    }
]

def body(j, traj, ans):
    slugs = [r["slug"] for r in GROUND_TRUTH]
    opened = opened_recipe(traj, slugs)
    j.check("opened_qualifying_recipe_detail", bool(opened),
            f"opened={[s for s in opened]}")
    named = [r for r in GROUND_TRUTH
            if r["slug"] in opened and mentions_title(ans, r["title"])]
    j.check("answer_names_opened_recipe", bool(named),
            f"named={[r['title'] for r in named]}")
    best = [r for r in named if mentions_number(ans, r["max_oven_temp"])]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--36", body)
