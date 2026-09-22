#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--39.

sushi rolls >=20 reviews + nutrition facts + main ingredients + storage

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
        "slug": "california-sushi-rolls",
        "title": "California Sushi Rolls",
        "avg_rating": "4.2",
        "review_count": 81,
        "nutrition": {
            "CALORIES": "320",
            "FAT": "8g",
            "CARBS": "48g",
            "PROTEIN": "18g",
            "SODIUM": "680mg",
            "IRON": "1.5mg",
            "CALCIUM": "40mg",
            "FIBER": "2g"
        },
        "ingredients": [
            "sushi rice",
            "rice vinegar",
            "sugar",
            "salt",
            "nori",
            "shrimp",
            "avocado",
            "soy sauce",
            "wasabi",
            "pickled ginger"
        ]
    },
    {
        "slug": "dragon-sushi-rolls",
        "title": "Dragon Sushi Rolls",
        "avg_rating": "3.8",
        "review_count": 100,
        "nutrition": {
            "CALORIES": "320",
            "FAT": "8g",
            "CARBS": "48g",
            "PROTEIN": "18g",
            "SODIUM": "680mg",
            "IRON": "1.5mg",
            "CALCIUM": "40mg",
            "FIBER": "2g"
        },
        "ingredients": [
            "sushi rice",
            "rice vinegar",
            "sugar",
            "salt",
            "nori",
            "shrimp tempura",
            "eel",
            "soy sauce",
            "wasabi",
            "pickled ginger"
        ]
    },
    {
        "slug": "salmon-avocado-sushi-rolls",
        "title": "Salmon Avocado Sushi Rolls",
        "avg_rating": "3.8",
        "review_count": 454,
        "nutrition": {
            "CALORIES": "320",
            "FAT": "8g",
            "CARBS": "48g",
            "PROTEIN": "18g",
            "SODIUM": "680mg",
            "IRON": "1.5mg",
            "CALCIUM": "40mg",
            "FIBER": "2g"
        },
        "ingredients": [
            "sushi rice",
            "rice vinegar",
            "sugar",
            "salt",
            "nori",
            "salmon",
            "avocado",
            "soy sauce",
            "wasabi",
            "pickled ginger"
        ]
    },
    {
        "slug": "spicy-tuna-sushi-rolls",
        "title": "Spicy Tuna Sushi Rolls",
        "avg_rating": "4.1",
        "review_count": 49,
        "nutrition": {
            "CALORIES": "320",
            "FAT": "8g",
            "CARBS": "48g",
            "PROTEIN": "18g",
            "SODIUM": "680mg",
            "IRON": "1.5mg",
            "CALCIUM": "40mg",
            "FIBER": "2g"
        },
        "ingredients": [
            "sushi rice",
            "rice vinegar",
            "sugar",
            "salt",
            "nori",
            "tuna",
            "cucumber",
            "soy sauce",
            "wasabi",
            "pickled ginger"
        ]
    },
    {
        "slug": "vegetable-sushi-rolls",
        "title": "Vegetable Sushi Rolls",
        "avg_rating": "4.7",
        "review_count": 47,
        "nutrition": {
            "CALORIES": "320",
            "FAT": "8g",
            "CARBS": "48g",
            "PROTEIN": "18g",
            "SODIUM": "680mg",
            "IRON": "1.5mg",
            "CALCIUM": "40mg",
            "FIBER": "2g"
        },
        "ingredients": [
            "sushi rice",
            "rice vinegar",
            "sugar",
            "salt",
            "nori",
            "cucumber",
            "avocado",
            "soy sauce",
            "wasabi",
            "pickled ginger"
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
    storage_ok = ("refrigerat" in ans.lower()
                  and any(w in ans.lower() for w in ("airtight", "sealed", "container")))
    best = [r for r in named
            if keyword_hits(ans, r["ingredients"]) >= 4 and nutrition_hits(ans, r["nutrition"]) >= 2]
    if best and not storage_ok:
        best = []
    j.check("answer_states_storage", storage_ok, "refrigerate + airtight/sealed container")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--39", body)
