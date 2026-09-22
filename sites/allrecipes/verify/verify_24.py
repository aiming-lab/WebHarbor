#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--24.

eggplant parmesan >=4.5 >50 reviews + prep time + servings

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
        "slug": "baked-eggplant-parmesan",
        "title": "Baked Eggplant Parmesan",
        "avg_rating": "4.6",
        "review_count": 64,
        "prep": "11 mins",
        "servings": "8"
    },
    {
        "slug": "classic-eggplant-parmesan",
        "title": "Classic Eggplant Parmesan",
        "avg_rating": "4.8",
        "review_count": 111,
        "prep": "43 mins",
        "servings": "6"
    },
    {
        "slug": "crispy-eggplant-parmesan",
        "title": "Crispy Eggplant Parmesan",
        "avg_rating": "4.8",
        "review_count": 88,
        "prep": "25 mins",
        "servings": "6"
    },
    {
        "slug": "easy-eggplant-parmesan",
        "title": "Easy Eggplant Parmesan",
        "avg_rating": "4.8",
        "review_count": 128,
        "prep": "15 mins",
        "servings": "4"
    },
    {
        "slug": "lightened-up-eggplant-parmesan",
        "title": "Lightened-Up Eggplant Parmesan",
        "avg_rating": "4.9",
        "review_count": 69,
        "prep": "13 mins",
        "servings": "6"
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
    best = [r for r in named
            if mentions_time(ans, r["prep"]) and mentions_number(ans, r["servings"])]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--24", body)
