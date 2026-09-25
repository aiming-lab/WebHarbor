#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--10.

Find The Most Popular Recipes of the 1960s; report the recipe name, prep time and total time of the SECOND recipe in the collection.

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened /collections/popular-1960s
   3. answer names the SECOND recipe in the collection
   4. answer states its prep time (15) and total time (40) as shown
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
GROUND_TRUTH = []

def body(j, traj, ans):
    j.check("opened_1960s_collection_page", opened_page(traj, "/collections/popular-1960s"),
            "task requires the Most Popular Recipes of the 1960s collection")
    j.check("answer_names_second_recipe", mentions_title(ans, "Chicken \u00e0 la King"),
            f"answer names the 2nd collection entry={mentions_title(ans, 'Chicken \u00e0 la King')}")
    j.check("answer_states_prep_time", mentions_number(ans, 15), "prep time 15 mins")
    j.check("answer_states_total_time", mentions_number(ans, 40), "total time 40 mins")

if __name__ == "__main__":
    run("Allrecipes--10", body)
