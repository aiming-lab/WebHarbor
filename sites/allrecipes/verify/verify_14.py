#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--14.

chicken breast + quinoa, prep <30 minutes

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened a /recipe/<slug> page from the qualifying set
   3. the answer names the qualifying recipe it opened
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
        "slug": "chicken-breast-and-quinoa-bowl",
        "title": "Chicken Breast and Quinoa Bowl",
        "avg_rating": "3.7",
        "review_count": 114
    },
    {
        "slug": "lemon-chicken-breast-with-quinoa",
        "title": "Lemon Chicken Breast with Quinoa",
        "avg_rating": "4.2",
        "review_count": 329
    },
    {
        "slug": "pesto-chicken-breast-quinoa-bowl",
        "title": "Pesto Chicken Breast Quinoa Bowl",
        "avg_rating": "4.4",
        "review_count": 123
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

if __name__ == "__main__":
    run("Allrecipes--14", body)
