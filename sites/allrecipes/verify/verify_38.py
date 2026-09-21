#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--38.

french ratatouille >=4 stars >=15 reviews + vegetables + cooking time

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
        "slug": "classic-french-ratatouille",
        "title": "Classic French Ratatouille",
        "avg_rating": "4.2",
        "review_count": 82,
        "cook": "1 hr 20 mins",
        "total": "1 hr 44 mins",
        "ingredients": [
            "eggplant",
            "zucchini",
            "squash",
            "bell pepper",
            "tomatoes",
            "onion",
            "garlic",
            "olive oil",
            "thyme",
            "basil"
        ]
    },
    {
        "slug": "oven-baked-french-ratatouille",
        "title": "Oven-Baked French Ratatouille",
        "avg_rating": "4.3",
        "review_count": 61,
        "cook": "2 hrs 52 mins",
        "total": "3 hrs 25 mins",
        "ingredients": [
            "eggplant",
            "zucchini",
            "bell pepper",
            "tomatoes",
            "garlic",
            "olive oil",
            "thyme",
            "basil"
        ]
    },
    {
        "slug": "proven%C3%A7al-ratatouille",
        "title": "Provençal Ratatouille",
        "avg_rating": "4.2",
        "review_count": 70,
        "cook": "25 mins",
        "total": "42 mins",
        "ingredients": [
            "eggplant",
            "zucchini",
            "bell pepper",
            "tomatoes",
            "onion",
            "garlic",
            "olive oil",
            "thyme",
            "basil"
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
    veg_words = ["eggplant", "zucchini", "squash", "bell pepper", "tomato", "onion", "garlic"]
    veg_hits = keyword_hits(ans, veg_words)
    time_ok = any(mentions_time(ans, r["cook"]) or mentions_time(ans, r["total"]) for r in named)
    best = named if (veg_hits >= 3 and time_ok) else []
    j.check("answer_states_vegetables", veg_hits >= 3, f"veg_hits={veg_hits}")
    j.check("answer_states_cooking_time", time_ok, "cook or total time stated")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--38", body)
