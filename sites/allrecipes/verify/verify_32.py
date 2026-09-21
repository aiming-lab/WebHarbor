#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--32.

slow cooker beef stew >=30 reviews + cooking time + first five ingredients

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
        "slug": "best-slow-cooker-beef-stew",
        "title": "Best Slow Cooker Beef Stew",
        "avg_rating": "4.2",
        "review_count": 69,
        "cook": "2 hrs 10 mins",
        "ingredients": [
            "beef chuck",
            "carrots",
            "potatoes",
            "celery",
            "red wine",
            "garlic",
            "Worcestershire sauce",
            "flour",
            "salt",
            "black pepper",
            "bay leaves"
        ],
        "first5": [
            "beef chuck",
            "carrots",
            "potatoes",
            "celery",
            "red wine"
        ]
    },
    {
        "slug": "classic-crock-pot-beef-stew",
        "title": "Classic Crock Pot Beef Stew",
        "avg_rating": "4.1",
        "review_count": 80,
        "cook": "41 mins",
        "ingredients": [
            "beef stew meat",
            "carrots",
            "potatoes",
            "onion",
            "tomato paste",
            "garlic",
            "Worcestershire sauce",
            "flour",
            "salt",
            "black pepper",
            "bay leaves"
        ],
        "first5": [
            "beef stew meat",
            "carrots",
            "potatoes",
            "onion",
            "tomato paste"
        ]
    },
    {
        "slug": "hearty-slow-cooker-beef-stew",
        "title": "Hearty Slow Cooker Beef Stew",
        "avg_rating": "4.3",
        "review_count": 54,
        "cook": "3 hrs 22 mins",
        "ingredients": [
            "beef chuck roast",
            "carrots",
            "potatoes",
            "pearl onions",
            "beef broth",
            "garlic",
            "Worcestershire sauce",
            "flour",
            "salt",
            "black pepper",
            "bay leaves"
        ],
        "first5": [
            "beef chuck roast",
            "carrots",
            "potatoes",
            "pearl onions",
            "beef broth"
        ]
    },
    {
        "slug": "rustic-slow-cooker-beef-stew",
        "title": "Rustic Slow Cooker Beef Stew",
        "avg_rating": "4.9",
        "review_count": 41,
        "cook": "27 mins",
        "ingredients": [
            "beef chuck",
            "carrots",
            "turnips",
            "onion",
            "beef stock",
            "garlic",
            "Worcestershire sauce",
            "flour",
            "salt",
            "black pepper",
            "bay leaves"
        ],
        "first5": [
            "beef chuck",
            "carrots",
            "turnips",
            "onion",
            "beef stock"
        ]
    },
    {
        "slug": "slow-cooker-beef-stew",
        "title": "Slow Cooker Beef Stew",
        "avg_rating": "4.2",
        "review_count": 126,
        "cook": "10 mins",
        "ingredients": [
            "beef chuck",
            "carrots",
            "potatoes",
            "onion",
            "beef broth",
            "garlic",
            "Worcestershire sauce",
            "flour",
            "salt",
            "black pepper",
            "bay leaves"
        ],
        "first5": [
            "beef chuck",
            "carrots",
            "potatoes",
            "onion",
            "beef broth"
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
            if keyword_hits(ans, r["first5"]) >= 4 and mentions_time(ans, r["cook"])]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--32", body)
