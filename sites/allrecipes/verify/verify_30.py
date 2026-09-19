#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--30.

vegan smoothie bowl banana+leaves >20 reviews >=4 stars + ingredients + steps

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
        "slug": "green-vegan-smoothie-bowl",
        "title": "Green Vegan Smoothie Bowl",
        "avg_rating": "4.3",
        "review_count": 38,
        "prep": "11 mins",
        "ingredients": [
            "bananas",
            "spinach leaves",
            "almond milk",
            "chia seeds",
            "almond butter",
            "vanilla",
            "granola",
            "berries"
        ],
        "steps": [
            "blend bananas spinach leaves",
            "add chia seeds almond butter",
            "pour into bowls",
            "top with granola and berries"
        ]
    },
    {
        "slug": "vegan-acai-banana-smoothie-bowl",
        "title": "Vegan Acai Banana Smoothie Bowl",
        "avg_rating": "4.3",
        "review_count": 34,
        "prep": "20 mins",
        "ingredients": [
            "acai",
            "bananas",
            "spinach leaves",
            "almond milk",
            "chia seeds",
            "almond butter",
            "vanilla",
            "granola",
            "berries"
        ],
        "steps": [
            "blend bananas spinach leaves",
            "add chia seeds almond butter",
            "pour into bowls",
            "top with granola and berries"
        ]
    },
    {
        "slug": "vegan-banana-kale-smoothie-bowl",
        "title": "Vegan Banana Kale Smoothie Bowl",
        "avg_rating": "4.5",
        "review_count": 89,
        "prep": "58 mins",
        "ingredients": [
            "bananas",
            "spinach leaves",
            "almond milk",
            "chia seeds",
            "almond butter",
            "vanilla",
            "granola",
            "berries"
        ],
        "steps": [
            "blend bananas spinach leaves",
            "add chia seeds almond butter",
            "pour into bowls",
            "top with granola and berries"
        ]
    },
    {
        "slug": "vegan-banana-spinach-smoothie-bowl",
        "title": "Vegan Banana Spinach Smoothie Bowl",
        "avg_rating": "4.4",
        "review_count": 81,
        "prep": "19 mins",
        "ingredients": [
            "bananas",
            "spinach leaves",
            "almond milk",
            "chia seeds",
            "almond butter",
            "vanilla",
            "granola",
            "berries"
        ],
        "steps": [
            "blend bananas spinach leaves",
            "add chia seeds almond butter",
            "pour into bowls",
            "top with granola and berries"
        ]
    },
    {
        "slug": "vegan-tropical-banana-smoothie-bowl",
        "title": "Vegan Tropical Banana Smoothie Bowl",
        "avg_rating": "4.1",
        "review_count": 441,
        "prep": "20 mins",
        "ingredients": [
            "bananas",
            "spinach leaves",
            "almond milk",
            "chia seeds",
            "almond butter",
            "vanilla",
            "granola",
            "berries"
        ],
        "steps": [
            "blend bananas spinach leaves",
            "add chia seeds almond butter",
            "pour into bowls",
            "top with granola and berries"
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
    banana_ok = keyword_hit(ans, "banana")
    leaf_ok = mentions_any(ans, ["spinach", "kale", "greens", "leaves"])
    best = [r for r in named
            if keyword_hits(ans, r["ingredients"]) >= 4 and mentions_time(ans, r["prep"])
            and keyword_hits(ans, r["steps"]) >= 2]
    if best and not (banana_ok and leaf_ok):
        best = []
    j.check("answer_states_banana_and_leaves", banana_ok and leaf_ok,
            f"banana={banana_ok} leafy-greens={leaf_ok}")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--30", body)
