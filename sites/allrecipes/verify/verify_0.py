#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--0.

vegetarian lasagna, >100 reviews, >=4.5 stars, suitable for 6 people

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened a /recipe/<slug> page from the qualifying set
   3. the answer names the qualifying recipe it opened

Qualifying-set note (audited): "suitable for 6 people" is graded as the
recipe being able to feed 6 people — the info-bar servings count is at least
6 (every qualifying recipe below has 6 or 8 servings), or the answer carries
an explicit scaling/adaptation note for 6 servings. The adjudicated rule
(acceptor CONVERGED + orchestrator ruling) is recorded in the task's
judge_rubric; the scaling arm has no catalog candidates: every vegetarian
lasagna that passes the >100-review and >=4.5-star constraints already shows
6, 8, 10 or 12 servings on its page, so no <6-serving recipe can ever be
graded here. The stricter reading "info bar shows exactly 6" matches only
two seeded recipes (Easy Vegetarian Spinach Lasagna, Keto Vegetarian
Lasagna) and was rejected because nine independent real-agent runs
consistently read the task's wording as suitability — see REPORT.md's
task-quality audit for the full evidence.
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
        "slug": "easy-vegetarian-spinach-lasagna",
        "title": "Easy Vegetarian Spinach Lasagna",
        "avg_rating": "4.8",
        "review_count": 128,
        "servings": "6"
    },
    {
        "slug": "keto-vegetarian-lasagna",
        "title": "Keto Vegetarian Lasagna",
        "avg_rating": "4.7",
        "review_count": 129,
        "servings": "6"
    },
    {
        "slug": "easy-vegan-lasagna",
        "title": "Easy Vegan Lasagna",
        "avg_rating": "4.7",
        "review_count": 120,
        "servings": "8"
    },
    {
        "slug": "mushroom-and-spinach-vegetarian-lasagna",
        "title": "Mushroom and Spinach Vegetarian Lasagna",
        "avg_rating": "4.8",
        "review_count": 470,
        "servings": "8"
    },
    {
        "slug": "vegetarian-zucchini-lasagna",
        "title": "Vegetarian Zucchini Lasagna",
        "avg_rating": "4.8",
        "review_count": 952,
        "servings": "8"
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

if __name__ == "__main__":
    run("Allrecipes--0", body)
