#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--21.

gluten-free brownies >=50 reviews high-rated + main ingredients + total time

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
        "slug": "almond-flour-gluten-free-brownies",
        "title": "Almond Flour Gluten-Free Brownies",
        "avg_rating": "4.3",
        "review_count": 86,
        "prep": "24 mins",
        "cook": "1 hr 32 mins",
        "total": "1 hr 56 mins",
        "ingredients": [
            "gluten-free flour",
            "cocoa powder",
            "sugar",
            "butter",
            "eggs",
            "vanilla",
            "baking powder",
            "salt",
            "chocolate chips"
        ]
    },
    {
        "slug": "chocolate-chunk-gluten-free-brownies",
        "title": "Chocolate Chunk Gluten-Free Brownies",
        "avg_rating": "4.2",
        "review_count": 113,
        "prep": "5 mins",
        "cook": "5 mins",
        "total": "10 mins",
        "ingredients": [
            "gluten-free flour",
            "cocoa powder",
            "sugar",
            "butter",
            "eggs",
            "vanilla",
            "baking powder",
            "salt",
            "chocolate chips"
        ]
    },
    {
        "slug": "fudgy-gluten-free-brownies",
        "title": "Fudgy Gluten-Free Brownies",
        "avg_rating": "4.1",
        "review_count": 150,
        "prep": "1 hr",
        "cook": "10 hrs 50 mins",
        "total": "11 hrs 50 mins",
        "ingredients": [
            "gluten-free flour",
            "cocoa powder",
            "sugar",
            "butter",
            "eggs",
            "vanilla",
            "baking powder",
            "salt",
            "chocolate chips"
        ]
    },
    {
        "slug": "gluten-free-vegan-brownies",
        "title": "Gluten-Free Vegan Brownies",
        "avg_rating": "4.7",
        "review_count": 120,
        "prep": "21 mins",
        "cook": "1 hr 17 mins",
        "total": "1 hr 38 mins",
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
            and (mentions_time(ans, r["total"])
                 or (mentions_time(ans, r["prep"]) and mentions_time(ans, r["cook"])))]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--21", body)
