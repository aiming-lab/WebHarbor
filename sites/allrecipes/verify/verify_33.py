#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--33.

low-carb breakfast >=25 reviews + nutrition facts + total carbs/serving

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
        "slug": "keto-low-carb-breakfast-bowl",
        "title": "Keto Low-Carb Breakfast Bowl",
        "avg_rating": "4.1",
        "review_count": 86,
        "nutrition": {
            "CALORIES": "380",
            "FAT": "28g",
            "TOTAL CARBOHYDRATE": "5g",
            "PROTEIN": "26g",
            "SODIUM": "620mg",
            "IRON": "2.5mg"
        }
    },
    {
        "slug": "low-carb-bacon-egg-cups",
        "title": "Low-Carb Bacon Egg Cups",
        "avg_rating": "4.2",
        "review_count": 274,
        "nutrition": {
            "CALORIES": "310",
            "FAT": "23g",
            "TOTAL CARBOHYDRATE": "2g",
            "PROTEIN": "24g",
            "SODIUM": "710mg",
            "IRON": "1.8mg"
        }
    },
    {
        "slug": "low-carb-breakfast-casserole",
        "title": "Low-Carb Breakfast Casserole",
        "avg_rating": "4.2",
        "review_count": 65,
        "nutrition": {
            "CALORIES": "320",
            "FAT": "24g",
            "TOTAL CARBOHYDRATE": "6g",
            "PROTEIN": "22g",
            "SODIUM": "580mg",
            "IRON": "2mg"
        }
    },
    {
        "slug": "spinach-feta-low-carb-breakfast",
        "title": "Spinach Feta Low-Carb Breakfast",
        "avg_rating": "4.9",
        "review_count": 81,
        "nutrition": {
            "CALORIES": "260",
            "FAT": "18g",
            "TOTAL CARBOHYDRATE": "4g",
            "PROTEIN": "20g",
            "SODIUM": "520mg",
            "IRON": "2mg"
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
    best = []
    for r in named:
        carbs = re.match(r"(\d+(?:\.\d+)?)", r["nutrition"].get("TOTAL CARBOHYDRATE", ""))
        if carbs and mentions_number(ans, carbs.group(1)) and nutrition_hits(ans, r["nutrition"]) >= 2:
            best.append(r)
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--33", body)
