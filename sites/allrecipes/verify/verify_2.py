#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--2.

vegetarian lasagna, <600 cal/serving, prep <1 hour

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
        "slug": "10-ingredient-vegan-lasagna",
        "title": "10-Ingredient Vegan Lasagna",
        "avg_rating": "4.3",
        "review_count": 359,
        "calories": "313",
        "nutrition_calories": "360"
    },
    {
        "slug": "easy-vegan-lasagna",
        "title": "Easy Vegan Lasagna",
        "avg_rating": "4.7",
        "review_count": 120,
        "calories": "584",
        "nutrition_calories": "360"
    },
    {
        "slug": "mushroom-and-spinach-vegetarian-lasagna",
        "title": "Mushroom and Spinach Vegetarian Lasagna",
        "avg_rating": "4.8",
        "review_count": 470,
        "calories": "330",
        "nutrition_calories": "540"
    },
    {
        "slug": "vegan-lentil-lasagna",
        "title": "Vegan Lentil Lasagna",
        "avg_rating": "4.2",
        "review_count": 422,
        "calories": "568",
        "nutrition_calories": "380"
    },
    {
        "slug": "vegetarian-zucchini-lasagna",
        "title": "Vegetarian Zucchini Lasagna",
        "avg_rating": "4.8",
        "review_count": 952,
        "calories": "492",
        "nutrition_calories": "420"
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
    run("Allrecipes--2", body)
