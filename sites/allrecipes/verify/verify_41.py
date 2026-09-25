#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--41.

List 3 recommended dinner recipes in the Allrecipes Dinners section.

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened one of the mirror's two Dinners sections: the /dinners
      landing page ("Recommended Dinner Recipes") or the Dinners category page
      (/category/dinner — the site's own top-nav "Dinners" link)
   3. the answer lists >=3 recipes shown on the Dinners section it opened
Input/Output: see verify_lib.run / Judge.emit.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run, opened_recipe, opened_page, mentions_title,
                        mentions_number, mentions_time, keyword_hit, keyword_hits,
                        mentions_any, nutrition_hits)

# Ground truth frozen from the mirror's own pages: the recipe cards each
# Dinners section actually shows.
GROUND_TRUTH = [
    {
        "page": "/dinners",
        "recommended": ["Low-Carb Cauliflower Pizza Base", "Traditional Fish Fry", "Valencian Seafood Paella", "Mediterranean Chicken Quinoa", "Vegetarian Zucchini Lasagna", "Maple Glazed Baked Salmon", "Roasted Veggie Lasagna", "Classic Beef Wellington", "Mushroom and Spinach Vegetarian Lasagna", "Salmon Avocado Sushi Rolls", "Crispy Baked Lemon Chicken Thighs", "Vegan Lentil Lasagna"]
    },
    {
        "page": "/category/dinner",
        "recommended": ["Easy Meatloaf", "World's Best Lasagna", "Chicken Tacos", "Beef Stroganoff", "Shiitake Fried Rice", "Low-Carb Cauliflower Pizza Base", "Traditional Fish Fry", "Valencian Seafood Paella", "Mediterranean Chicken Quinoa", "Vegetarian Zucchini Lasagna", "Maple Glazed Baked Salmon", "Roasted Veggie Lasagna"]
    }
]

def body(j, traj, ans):
    opened = [r for r in GROUND_TRUTH if opened_page(traj, r["page"])]
    j.check("opened_dinners_section", bool(opened),
            f"opened={[r['page'] for r in opened]} "
            f"(either /dinners or the Dinners category page)")
    listed = 0
    hits = []
    for r in opened:
        hits = [t for t in r["recommended"] if mentions_title(ans, t)]
        listed = max(listed, len(hits))
    j.check("answer_lists_recommended_dinners", listed >= 3,
            f"matched_titles={hits}")

if __name__ == "__main__":
    run("Allrecipes--41", body)
