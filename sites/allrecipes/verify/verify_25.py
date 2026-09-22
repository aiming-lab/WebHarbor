#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--25.

quinoa salad >500 reviews >4 stars + shopping list + times

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
        "slug": "black-bean-quinoa-salad",
        "title": "Black Bean Quinoa Salad",
        "avg_rating": "4.5",
        "review_count": 670,
        "prep": "17 mins",
        "cook": "41 mins",
        "total": "58 mins",
        "ingredients": [
            "quinoa",
            "water",
            "cucumber",
            "cherry tomatoes",
            "red onion",
            "feta cheese",
            "olive oil",
            "lemon juice",
            "parsley",
            "salt"
        ]
    },
    {
        "slug": "lemon-herb-quinoa-salad",
        "title": "Lemon Herb Quinoa Salad",
        "avg_rating": "4.4",
        "review_count": 723,
        "prep": "5 mins",
        "cook": "6 mins",
        "total": "11 mins",
        "ingredients": [
            "quinoa",
            "water",
            "cucumber",
            "cherry tomatoes",
            "red onion",
            "feta cheese",
            "olive oil",
            "lemon juice",
            "parsley",
            "salt"
        ]
    },
    {
        "slug": "mediterranean-quinoa-salad",
        "title": "Mediterranean Quinoa Salad",
        "avg_rating": "4.4",
        "review_count": 997,
        "prep": "16 mins",
        "cook": "41 mins",
        "total": "57 mins",
        "ingredients": [
            "quinoa",
            "water",
            "cucumber",
            "cherry tomatoes",
            "red onion",
            "feta cheese",
            "olive oil",
            "lemon juice",
            "parsley",
            "salt"
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
            if keyword_hits(ans, r["ingredients"]) >= 5 and mentions_time(ans, r["prep"])
            and (mentions_time(ans, r["cook"]) or mentions_time(ans, r["total"]))]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--25", body)
