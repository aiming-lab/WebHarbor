#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--26.

high-protein vegetarian chili >=50 reviews >=4 stars + ingredients + time + steps

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
        "slug": "high-protein-vegetarian-chili",
        "title": "High-Protein Vegetarian Chili",
        "avg_rating": "4.4",
        "review_count": 132,
        "cook": "7 hrs 5 mins",
        "ingredients": [
            "black beans",
            "kidney beans",
            "lentils",
            "quinoa",
            "crushed tomatoes",
            "onion",
            "garlic",
            "chili powder",
            "cumin",
            "salt"
        ],
        "steps": [
            "saute onion and garlic",
            "add spices and cook 1",
            "stir in beans lentils tomatoes",
            "simmer 40 minutes until thickened"
        ]
    },
    {
        "slug": "spicy-vegetarian-chili",
        "title": "Spicy Vegetarian Chili",
        "avg_rating": "4.5",
        "review_count": 147,
        "cook": "1 hr 32 mins",
        "ingredients": [
            "black beans",
            "kidney beans",
            "lentils",
            "quinoa",
            "crushed tomatoes",
            "onion",
            "garlic",
            "chili powder",
            "cumin",
            "salt"
        ],
        "steps": [
            "saute onion and garlic",
            "add spices and cook 1",
            "stir in beans lentils tomatoes",
            "simmer 40 minutes until thickened"
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
            if keyword_hits(ans, r["ingredients"]) >= 5 and mentions_time(ans, r["cook"])
            and keyword_hits(ans, r["steps"]) >= 2]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--26", body)
