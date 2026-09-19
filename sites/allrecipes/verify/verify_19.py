#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--19.

vegan lasagna <=10 ingredients >200 reviews + overview + times

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
        "slug": "10-ingredient-vegan-lasagna",
        "title": "10-Ingredient Vegan Lasagna",
        "avg_rating": "4.3",
        "review_count": 359,
        "prep": "15 mins",
        "cook": "2 hrs 1 mins",
        "ingredients": [
            "lasagna noodles",
            "vegan ricotta",
            "spinach",
            "marinara sauce",
            "vegan mozzarella",
            "olive oil",
            "garlic",
            "italian seasoning",
            "salt",
            "pepper"
        ]
    },
    {
        "slug": "simple-vegan-lasagna",
        "title": "Simple Vegan Lasagna",
        "avg_rating": "4.2",
        "review_count": 292,
        "prep": "14 mins",
        "cook": "1 hr 44 mins",
        "ingredients": [
            "lasagna noodles",
            "tofu",
            "spinach",
            "marinara",
            "nutritional yeast",
            "garlic",
            "olive oil",
            "basil",
            "salt",
            "pepper"
        ]
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
            if keyword_hits(ans, r["ingredients"]) >= 4
            and mentions_time(ans, r["prep"]) and mentions_time(ans, r["cook"])]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--19", body)
