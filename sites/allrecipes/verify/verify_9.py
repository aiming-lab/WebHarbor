#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--9.

high-rated vegetarian lasagna + key ingredients + prep/cook time

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
        "slug": "easy-vegan-lasagna",
        "title": "Easy Vegan Lasagna",
        "avg_rating": "4.7",
        "review_count": 120,
        "prep": "16 mins",
        "cook": "34 mins",
        "ingredients": [
            "lasagna noodles",
            "vegan ricotta",
            "marinara",
            "zucchini",
            "spinach",
            "garlic",
            "olive oil",
            "italian herbs",
            "salt"
        ]
    },
    {
        "slug": "easy-vegetarian-spinach-lasagna",
        "title": "Easy Vegetarian Spinach Lasagna",
        "avg_rating": "4.8",
        "review_count": 128,
        "prep": "1 hr 59 mins",
        "cook": "41 mins",
        "ingredients": [
            "lasagna noodles",
            "ricotta cheese",
            "mozzarella",
            "Parmesan cheese",
            "crushed tomatoes",
            "garlic",
            "Italian seasoning",
            "olive oil",
            "salt",
            "black pepper",
            "spinach"
        ]
    },
    {
        "slug": "keto-vegetarian-lasagna",
        "title": "Keto Vegetarian Lasagna",
        "avg_rating": "4.7",
        "review_count": 129,
        "prep": "1 hr 20 mins",
        "cook": "1 hr 6 mins",
        "ingredients": [
            "zucchini sliced thin",
            "lasagna noodles",
            "ricotta cheese",
            "mozzarella",
            "Parmesan cheese",
            "crushed tomatoes",
            "garlic",
            "Italian seasoning",
            "olive oil",
            "salt",
            "black pepper"
        ]
    },
    {
        "slug": "mushroom-and-spinach-vegetarian-lasagna",
        "title": "Mushroom and Spinach Vegetarian Lasagna",
        "avg_rating": "4.8",
        "review_count": 470,
        "prep": "55 mins",
        "cook": "1 hr 3 mins",
        "ingredients": [
            "lasagna noodles",
            "ricotta cheese",
            "mozzarella",
            "Parmesan cheese",
            "crushed tomatoes",
            "garlic",
            "Italian seasoning",
            "olive oil",
            "salt",
            "black pepper",
            "frozen spinach thawed",
            "mushrooms"
        ]
    },
    {
        "slug": "vegetarian-zucchini-lasagna",
        "title": "Vegetarian Zucchini Lasagna",
        "avg_rating": "4.8",
        "review_count": 952,
        "prep": "28 mins",
        "cook": "57 mins",
        "ingredients": [
            "zucchini sliced thin",
            "lasagna noodles",
            "ricotta cheese",
            "mozzarella",
            "Parmesan cheese",
            "crushed tomatoes",
            "garlic",
            "Italian seasoning",
            "olive oil",
            "salt",
            "black pepper"
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
    run("Allrecipes--9", body)
