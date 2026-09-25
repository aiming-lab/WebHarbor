#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--26.

Latest report on the impact of recent natural disasters in Asia.

The Asia section lead among the natural-disaster stories is 'Asia:
Philippines typhoon leaves 80 dead and displaces half a million'
(13 Apr 2026). Checks: opened that article; the answer states the
typhoon's toll and affected areas.

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

CONTEXT_PAGES = ["/news/asia"]
CONTEXT_SEARCHES = ["natural disaster", "typhoon", "asia"]
GROUND_TRUTH = [
 {
  "slug": "asia-philippines-typhoon-leaves-80-dead-and-displaces-half-a-million",
  "title": "Asia: Philippines typhoon leaves 80 dead and displaces half a million",
  "facts": [
   [
    "philippines"
   ],
   [
    "typhoon",
    "storm"
   ],
   [
    "80 dead",
    "80 deaths",
    "80 people",
    "80"
   ],
   [
    "half a million",
    "500,000",
    "500000",
    "displaced"
   ],
   [
    "samar",
    "leyte",
    "cebu"
   ]
  ],
  "min_facts": 3
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
    run("BBC News--26", body)
