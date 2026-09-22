#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--30.

Culture section: the latest film release reviewed.

The Culture section's newest film review is 'Film review: The Last
Horizon' is a stunning and emotional sci-fi epic' (14 Apr 2026).
Checks: opened that review; the answer names the film and its review's
substance.

Input/Output: see verify_lib.run / Judge.emit. Ground truth below is frozen
from the mirror's own pages (section listings + article detail text).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run, opened_article, opened_page, searched,
                        mentions_title, mentions_title_frac, mentions_number,
                        mentions_group, group_hits, mentions_date, last_shot,
                        llm_text_match, llm_screenshot_shows, norm)

CONTEXT_PAGES = ["/news/culture", "/news/film", "/latest"]
CONTEXT_SEARCHES = ["film review"]
GROUND_TRUTH = [
 {
  "slug": "film-review-the-last-horizon-is-a-stunning-and-emotional-sci-fi-epic",
  "title": "Film review: 'The Last Horizon' is a stunning and emotional sci-fi epic",
  "facts": [
   [
    "the last horizon",
    "last horizon"
   ],
   [
    "sci-fi",
    "sci fi",
    "science fiction"
   ],
   [
    "villeneuve"
   ],
   [
    "florence pugh",
    "mahershala ali"
   ],
   [
    "five-star",
    "five star",
    "stunning",
    "emotional"
   ]
  ],
  "min_facts": 2
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)


def body(j, traj, ans):
    opened = opened_article(traj, [g["slug"] for g in GROUND_TRUTH])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    if opened:
        j.evidence.append(f"[note] opened detail page(s): {opened}")
    matched = [g for g in GROUND_TRUTH
               if group_hits(ans, g["facts"]) >= g["min_facts"]]
    bound = [g for g in matched if g["slug"] in opened] if opened else matched
    j.check("answer_matches_qualifying_article", bool(bound),
            f"matched={[g['title'] for g in bound]} (facts from the "
            f"article's own page/listing card)")

if __name__ == "__main__":
    run("BBC News--30", body)
