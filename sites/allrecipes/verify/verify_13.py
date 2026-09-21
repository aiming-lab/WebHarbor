#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--13.

fried fish >100 reviews + full nutrition label + iron per serving

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
        "slug": "classic-beer-battered-fried-fish",
        "title": "Classic Beer Battered Fried Fish",
        "avg_rating": "4.2",
        "review_count": 163,
        "nutrition": {
            "CALORIES": "420",
            "FAT": "22g",
            "CARBS": "28g",
            "PROTEIN": "30g",
            "SODIUM": "720mg",
            "IRON": "2.4mg",
            "CALCIUM": "85mg",
            "FIBER": "1g",
            "CHOLESTEROL": "110mg"
        }
    },
    {
        "slug": "cornmeal-fried-catfish",
        "title": "Cornmeal Fried Catfish",
        "avg_rating": "4.2",
        "review_count": 191,
        "nutrition": {
            "CALORIES": "360",
            "FAT": "22g",
            "CARBS": "28g",
            "PROTEIN": "30g",
            "SODIUM": "720mg",
            "IRON": "2.4mg",
            "CALCIUM": "85mg",
            "CHOLESTEROL": "110mg"
        }
    },
    {
        "slug": "crispy-southern-fried-fish",
        "title": "Crispy Southern Fried Fish",
        "avg_rating": "4.3",
        "review_count": 189,
        "nutrition": {
            "CALORIES": "390",
            "FAT": "22g",
            "CARBS": "28g",
            "PROTEIN": "30g",
            "SODIUM": "720mg",
            "IRON": "2.4mg",
            "CALCIUM": "85mg",
            "FIBER": "1g",
            "CHOLESTEROL": "110mg"
        }
    },
    {
        "slug": "pan-fried-fish-fillets",
        "title": "Pan-Fried Fish Fillets",
        "avg_rating": "3.4",
        "review_count": 176,
        "nutrition": {
            "CALORIES": "310",
            "FAT": "22g",
            "CARBS": "28g",
            "PROTEIN": "30g",
            "SODIUM": "720mg",
            "IRON": "2.4mg",
            "CALCIUM": "85mg",
            "FIBER": "1g",
            "CHOLESTEROL": "110mg"
        }
    },
    {
        "slug": "traditional-fish-fry",
        "title": "Traditional Fish Fry",
        "avg_rating": "3.2",
        "review_count": 8861,
        "nutrition": {
            "CALORIES": "400",
            "FAT": "22g",
            "CARBS": "28g",
            "PROTEIN": "30g",
            "SODIUM": "720mg",
            "IRON": "2.4mg",
            "CALCIUM": "85mg",
            "FIBER": "1g",
            "CHOLESTEROL": "110mg"
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
    iron = 2.4  # mg per serving shown in every qualifying recipe's Nutrition Facts
    best = [r for r in named
            if mentions_number(ans, iron) and nutrition_hits(ans, r["nutrition"]) >= 3]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--13", body)
