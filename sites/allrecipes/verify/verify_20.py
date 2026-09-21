#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--20.

cauliflower pizza crust, prep <30 min, >=4 stars + calories/serving

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
        "slug": "crispy-cauliflower-pizza-crust",
        "title": "Crispy Cauliflower Pizza Crust",
        "avg_rating": "4.4",
        "review_count": 301,
        "calories": "752",
        "nutrition_calories": "160"
    },
    {
        "slug": "easy-cauliflower-pizza-crust",
        "title": "Easy Cauliflower Pizza Crust",
        "avg_rating": "4.2",
        "review_count": 171,
        "calories": "1240",
        "nutrition_calories": "180"
    },
    {
        "slug": "keto-cauliflower-pizza-crust",
        "title": "Keto Cauliflower Pizza Crust",
        "avg_rating": "4.2",
        "review_count": 54,
        "calories": "687",
        "nutrition_calories": "145"
    },
    {
        "slug": "low-carb-cauliflower-pizza-base",
        "title": "Low-Carb Cauliflower Pizza Base",
        "avg_rating": "4.7",
        "review_count": 9937,
        "calories": "611",
        "nutrition_calories": "155"
    },
    {
        "slug": "gluten-free-cauliflower-crust",
        "title": "Gluten-Free Cauliflower Crust",
        "avg_rating": "4.3",
        "review_count": 4,
        "calories": "294",
        "nutrition_calories": "170"
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
            if mentions_number(ans, r["calories"])
            or (r["nutrition_calories"] and mentions_number(ans, r["nutrition_calories"]))]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--20", body)
