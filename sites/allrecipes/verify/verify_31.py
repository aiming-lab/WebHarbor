#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--31.

seafood paella >=4.5 >=50 reviews shrimp+mussels + ingredients + time + steps

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
        "slug": "classic-seafood-paella",
        "title": "Classic Seafood Paella",
        "avg_rating": "4.9",
        "review_count": 141,
        "total": "59 mins",
        "ingredients": [
            "bomba rice",
            "shrimp",
            "mussels",
            "onion",
            "garlic",
            "red bell pepper",
            "saffron",
            "seafood broth",
            "olive oil",
            "smoked paprika",
            "lemon",
            "parsley"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "traditional-spanish-seafood-paella",
        "title": "Traditional Spanish Seafood Paella",
        "avg_rating": "4.7",
        "review_count": 125,
        "total": "7 hrs 26 mins",
        "ingredients": [
            "bomba rice",
            "shrimp",
            "mussels",
            "onion",
            "garlic",
            "red bell pepper",
            "saffron",
            "seafood broth",
            "olive oil",
            "smoked paprika",
            "lemon",
            "parsley"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
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
    shrimp_ok = keyword_hit(ans, "shrimp")
    mussels_ok = keyword_hit(ans, "mussels")
    best = [r for r in named
            if keyword_hits(ans, r["ingredients"]) >= 5 and mentions_time(ans, r["total"])
            and keyword_hits(ans, r["steps"]) >= 2]
    if best and not (shrimp_ok and mussels_ok):
        best = []
    j.check("answer_states_shrimp_and_mussels", shrimp_ok and mussels_ok,
            f"shrimp={shrimp_ok} mussels={mussels_ok}")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--31", body)
