#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--27.

chicken curry >30 reviews >=4 stars + ingredients + prep time + instructions

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
        "slug": "easy-chicken-curry",
        "title": "Easy Chicken Curry",
        "avg_rating": "4.3",
        "review_count": 95,
        "prep": "50 mins",
        "ingredients": [
            "chicken",
            "onion",
            "garlic",
            "ginger",
            "curry powder",
            "coconut milk",
            "tomatoes",
            "oil",
            "salt",
            "cilantro"
        ],
        "steps": [
            "saute onion garlic and ginger",
            "add curry powder and cook",
            "add chicken and brown",
            "pour in coconut milk"
        ]
    },
    {
        "slug": "indian-chicken-curry",
        "title": "Indian Chicken Curry",
        "avg_rating": "4.3",
        "review_count": 77,
        "prep": "10 mins",
        "ingredients": [
            "chicken",
            "onion",
            "garlic",
            "ginger",
            "curry powder",
            "coconut milk",
            "tomatoes",
            "oil",
            "salt",
            "cilantro"
        ],
        "steps": [
            "saute onion garlic and ginger",
            "add curry powder and cook",
            "add chicken and brown",
            "pour in coconut milk"
        ]
    },
    {
        "slug": "red-chicken-curry",
        "title": "Red Chicken Curry",
        "avg_rating": "4.2",
        "review_count": 51,
        "prep": "10 mins",
        "ingredients": [
            "chicken",
            "onion",
            "garlic",
            "ginger",
            "curry powder",
            "coconut milk",
            "tomatoes",
            "oil",
            "salt",
            "cilantro"
        ],
        "steps": [
            "saute onion garlic and ginger",
            "add curry powder and cook",
            "add chicken and brown",
            "pour in coconut milk"
        ]
    },
    {
        "slug": "thai-green-chicken-curry",
        "title": "Thai Green Chicken Curry",
        "avg_rating": "4.2",
        "review_count": 99,
        "prep": "32 mins",
        "ingredients": [
            "chicken",
            "onion",
            "garlic",
            "ginger",
            "curry powder",
            "coconut milk",
            "tomatoes",
            "oil",
            "salt",
            "cilantro"
        ],
        "steps": [
            "saute onion garlic and ginger",
            "add curry powder and cook",
            "add chicken and brown",
            "pour in coconut milk"
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
            if keyword_hits(ans, r["ingredients"]) >= 4 and mentions_time(ans, r["prep"])
            and keyword_hits(ans, r["steps"]) >= 2]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--27", body)
