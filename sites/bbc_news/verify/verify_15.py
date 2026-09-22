#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--15.

What the current headline in Natural Wonders tells about.

The Natural Wonders section (/news/natural_wonders) lead is 'Natural
wonders: Iceland's Vatnajökull glacier retreat captured from the air'
(13 Apr 2026). Checks: opened that article; the answer conveys Iceland,
the glacier and the retreat.

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

CONTEXT_PAGES = ["/news/natural_wonders", "/latest"]
CONTEXT_SEARCHES = ["natural wonders"]
GROUND_TRUTH = [
 {
  "slug": "natural-wonders-iceland-s-vatnajokull-glacier-retreat-captured-from-the-air",
  "title": "Natural wonders: Iceland's Vatnajökull glacier retreat captured from the air",
  "facts": [
   [
    "iceland"
   ],
   [
    "glacier"
   ],
   [
    "vatnajokull",
    "vatnajökull"
   ],
   [
    "retreat",
    "retreating",
    "80 metres",
    "80 meters",
    "melting",
    "shrinking"
   ],
   [
    "bbc earth",
    "camera crew",
    "three summers"
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
    run("BBC News--15", body)
