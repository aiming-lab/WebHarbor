#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--29.

mediterranean grilled fish with olives >=4 stars >25 reviews + method + total time

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
        "slug": "greek-grilled-fish",
        "title": "Greek Grilled Fish",
        "avg_rating": "4.5",
        "review_count": 84,
        "total": "4 hrs 50 mins",
        "ingredients": [
            "fish fillets",
            "Kalamata olives",
            "olive oil",
            "garlic",
            "lemon",
            "oregano",
            "capers",
            "salt",
            "parsley"
        ]
    },
    {
        "slug": "grilled-mediterranean-fish-with-olives",
        "title": "Grilled Mediterranean Fish with Olives",
        "avg_rating": "4.4",
        "review_count": 74,
        "total": "15 mins",
        "ingredients": [
            "fish fillets",
            "Kalamata olives",
            "olive oil",
            "garlic",
            "lemon",
            "oregano",
            "capers",
            "salt",
            "parsley"
        ]
    },
    {
        "slug": "italian-grilled-branzino",
        "title": "Italian Grilled Branzino",
        "avg_rating": "4.0",
        "review_count": 278,
        "total": "18 mins",
        "ingredients": [
            "fish fillets",
            "Kalamata olives",
            "olive oil",
            "garlic",
            "lemon",
            "oregano",
            "capers",
            "salt",
            "parsley"
        ]
    },
    {
        "slug": "mediterranean-grilled-sea-bass",
        "title": "Mediterranean Grilled Sea Bass",
        "avg_rating": "4.5",
        "review_count": 99,
        "total": "13 mins",
        "ingredients": [
            "fish fillets",
            "Kalamata olives",
            "olive oil",
            "garlic",
            "lemon",
            "oregano",
            "capers",
            "salt",
            "parsley"
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
    method_ok = re.search(r"\bgrill", ans.lower()) is not None
    olives_ok = "olive" in ans.lower()
    best = [r for r in named
            if keyword_hits(ans, r["ingredients"]) >= 4 and mentions_time(ans, r["total"])]
    if best and not (method_ok and olives_ok):
        best = []
    j.check("answer_states_cooking_method_and_olives", method_ok and olives_ok,
            f"grill-mention={method_ok} olives-mention={olives_ok}")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--29", body)
