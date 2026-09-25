#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--35.

italian meatballs >100 reviews + meat type + cooking time

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
        "slug": "authentic-italian-meatballs",
        "title": "Authentic Italian Meatballs",
        "avg_rating": "4.2",
        "review_count": 206,
        "cook": "1 hr 10 mins",
        "total": "1 hr 29 mins"
    },
    {
        "slug": "baked-italian-meatballs",
        "title": "Baked Italian Meatballs",
        "avg_rating": "3.4",
        "review_count": 192,
        "cook": "2 hrs 27 mins",
        "total": "3 hrs 2 mins"
    },
    {
        "slug": "best-italian-meatballs",
        "title": "Best Italian Meatballs",
        "avg_rating": "4.2",
        "review_count": 225,
        "cook": "31 mins",
        "total": "45 mins"
    },
    {
        "slug": "classic-italian-meatballs",
        "title": "Classic Italian Meatballs",
        "avg_rating": "4.1",
        "review_count": 195,
        "cook": "1 hr 52 mins",
        "total": "2 hrs 12 mins"
    },
    {
        "slug": "easy-italian-meatballs",
        "title": "Easy Italian Meatballs",
        "avg_rating": "3.6",
        "review_count": 304,
        "cook": "10 hrs 23 mins",
        "total": "11 hrs 23 mins"
    },
    {
        "slug": "grandma-s-italian-meatballs",
        "title": "Grandma's Italian Meatballs",
        "avg_rating": "4.8",
        "review_count": 116,
        "cook": "33 mins",
        "total": "49 mins"
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
    beef_ok = keyword_hit(ans, "beef")
    best = [r for r in named
            if (mentions_time(ans, r["cook"]) or mentions_time(ans, r["total"]))]
    if best and not beef_ok:
        best = []
    j.check("answer_states_meat_type", beef_ok, f"beef-mention={beef_ok}")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--35", body)
