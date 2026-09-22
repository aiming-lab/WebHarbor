#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--35.

Asia section: the most recent report about technological advancements.

The Asia section's technology stories: 'Asia: Singapore unveils
regional quantum-computing hub' (9 Apr 2026) is the newest in the Asia
section; the section also carries the Indonesia satellite story and the
Japan humanoid-robot story. Checks: opened one of the three; the answer
summarizes that story's content.

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
CONTEXT_SEARCHES = ["asia", "technology"]
GROUND_TRUTH = [
 {
  "slug": "asia-singapore-unveils-regional-quantum-computing-hub",
  "title": "Asia: Singapore unveils regional quantum-computing hub",
  "facts": [
   [
    "singapore"
   ],
   [
    "quantum"
   ],
   [
    "astar",
    "ibm",
    "research hub"
   ],
   [
    "jurong"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "asia-indonesia-launches-first-indigenous-satellite-for-disaster-monito",
  "title": "Asia: Indonesia launches first indigenous satellite for disaster monitoring",
  "facts": [
   [
    "indonesia"
   ],
   [
    "satellite"
   ],
   [
    "lapan",
    "volcano",
    "disaster monitoring",
    "earth-observation"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "asia-tech-advancements-japan-unveils-humanoid-factory-robot-that-learn",
  "title": "Asia tech advancements: Japan unveils humanoid factory robot that learns on the job",
  "facts": [
   [
    "japan"
   ],
   [
    "humanoid",
    "robot"
   ],
   [
    "labour shortage",
    "labor shortage",
    "machine learning"
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
    run("BBC News--35", body)
