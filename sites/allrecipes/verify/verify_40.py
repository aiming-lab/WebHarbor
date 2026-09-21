#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--40.

Browse the about us section of Allrecipes for a brief introduction to The Allrecipes Allstars.

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened the About Us section (/about or the /about/allstars
      page it links to)
   3. the answer conveys the page's introduction of the Allstars program:
      it mentions the Allstars and carries at least three distinctive
      content fragments from the about pages' Allstars text
Input/Output: see verify_lib.run / Judge.emit.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run, opened_recipe, opened_page, mentions_title,
                        mentions_number, mentions_time, keyword_hit, keyword_hits,
                        mentions_any, nutrition_hits)

# Ground truth frozen from the mirror's own pages.
GROUND_TRUTH = [
    {
        "page": "/about",
        "allstars": ["Chef John", "Nicole McLaughlin", "Juliana Hale",
                     "Bren Herrera", "Ann Taylor Pittman"]
    },
    {
        "page": "/about/allstars",
        "allstars": ["Chef John", "Nicole McLaughlin", "Juliana Hale",
                     "Bren Herrera", "Ann Taylor Pittman"]
    }
]

# Distinctive phrases from the Allstars introduction paragraphs actually
# rendered on /about and /about/allstars (audited from the pages).
INTRO_FRAGMENTS = [
    "home cooks", "food enthusiasts", "content creators", "test recipes",
    "share recipes", "cooking tips", "community", "real people",
    "real kitchens", "share photos", "leave helpful reviews",
    "original content", "authenticity", "shared love of food",
]

def body(j, traj, ans):
    seen = [r["page"] for r in GROUND_TRUTH if opened_page(traj, r["page"])]
    j.check("opened_about_pages", bool(seen), f"opened={seen}")
    mentions_allstars = "allstar" in ans.lower()
    j.check("answer_mentions_allstars", mentions_allstars, "the Allstars program")
    frags = [f for f in INTRO_FRAGMENTS if keyword_hit(ans, f)]
    j.check("answer_conveys_allstars_introduction", len(frags) >= 3,
            f"intro_fragments={frags}")

if __name__ == "__main__":
    run("Allrecipes--40", body)
