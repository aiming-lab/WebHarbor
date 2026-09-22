#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--28.

vegan brownie >=40 reviews >=4.5 + ingredients + prep/cook time + steps overview

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
        "slug": "chocolate-chunk-vegan-brownies",
        "title": "Chocolate Chunk Vegan Brownies",
        "avg_rating": "4.7",
        "review_count": 54,
        "prep": "13 mins",
        "cook": "11 mins",
        "ingredients": [
            "flour",
            "cocoa powder",
            "sugar",
            "vegan butter",
            "almond milk",
            "vanilla",
            "baking powder",
            "salt",
            "vegan chocolate chips"
        ]
    },
    {
        "slug": "fudgy-vegan-brownies",
        "title": "Fudgy Vegan Brownies",
        "avg_rating": "4.8",
        "review_count": 111,
        "prep": "37 mins",
        "cook": "1 hr 54 mins",
        "ingredients": [
            "flour",
            "cocoa powder",
            "sugar",
            "vegan butter",
            "almond milk",
            "vanilla",
            "baking powder",
            "salt",
            "vegan chocolate chips"
        ]
    },
    {
        "slug": "gluten-free-vegan-brownies",
        "title": "Gluten-Free Vegan Brownies",
        "avg_rating": "4.7",
        "review_count": 120,
        "prep": "21 mins",
        "cook": "1 hr 17 mins",
        "ingredients": [
            "flour",
            "cocoa powder",
            "sugar",
            "vegan butter",
            "almond milk",
            "vanilla",
            "baking powder",
            "salt",
            "vegan chocolate chips"
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
    run("Allrecipes--28", body)
