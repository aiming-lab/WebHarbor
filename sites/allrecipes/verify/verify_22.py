#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--22.

avocado salad prep <20 min >30 reviews + nutrition per serving

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
        "slug": "avocado-and-cucumber-salad",
        "title": "Avocado and Cucumber Salad",
        "avg_rating": "4.2",
        "review_count": 62,
        "calories": "356",
        "nutrition_calories": "200",
        "nutrition": {
            "CALORIES": "200",
            "FAT": "18g",
            "CARBS": "14g",
            "PROTEIN": "4g",
            "SODIUM": "160mg",
            "IRON": "1.2mg",
            "CALCIUM": "30mg",
            "FIBER": "9g",
            "SUGAR": "4g"
        }
    },
    {
        "slug": "avocado-chickpea-salad",
        "title": "Avocado Chickpea Salad",
        "avg_rating": "4.1",
        "review_count": 81,
        "calories": "871",
        "nutrition_calories": "290",
        "nutrition": {
            "CALORIES": "290",
            "FAT": "18g",
            "CARBS": "14g",
            "PROTEIN": "4g",
            "SODIUM": "160mg",
            "IRON": "1.2mg",
            "CALCIUM": "30mg",
            "FIBER": "9g",
            "SUGAR": "4g"
        }
    },
    {
        "slug": "healthy-avocado-salad",
        "title": "Healthy Avocado Salad",
        "avg_rating": "4.3",
        "review_count": 102,
        "calories": "349",
        "nutrition_calories": "240",
        "nutrition": {
            "CALORIES": "240",
            "FAT": "18g",
            "CARBS": "14g",
            "PROTEIN": "4g",
            "SODIUM": "160mg",
            "IRON": "1.2mg",
            "CALCIUM": "30mg",
            "FIBER": "9g",
            "SUGAR": "4g"
        }
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
            if (mentions_number(ans, r["nutrition_calories"]) or mentions_number(ans, r["calories"]))
            and nutrition_hits(ans, r["nutrition"]) >= 2]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--22", body)
