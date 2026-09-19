#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--37.

greek salad prep <25 min >15 reviews + primary cheese + dressing

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
        "slug": "authentic-greek-salad",
        "title": "Authentic Greek Salad",
        "avg_rating": "4.1",
        "review_count": 53
    },
    {
        "slug": "greek-salad",
        "title": "Greek Salad",
        "avg_rating": "4.5",
        "review_count": 169
    },
    {
        "slug": "simple-greek-salad",
        "title": "Simple Greek Salad",
        "avg_rating": "4.2",
        "review_count": 52
    },
    {
        "slug": "traditional-greek-village-salad",
        "title": "Traditional Greek Village Salad",
        "avg_rating": "4.2",
        "review_count": 44
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
    feta_ok = keyword_hit(ans, "feta")
    dressing_ok = mentions_any(ans, ["red wine vinegar", "vinaigrette", "dressing", "vinegar"])
    best = named if (feta_ok and dressing_ok) else []
    j.check("answer_states_cheese_and_dressing", feta_ok and dressing_ok,
            f"feta={feta_ok} dressing={dressing_ok}")
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--37", body)
