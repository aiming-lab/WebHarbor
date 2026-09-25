#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--27.

Most recent article about archaeological discoveries, its findings and
significance.

AUDIT NOTE (flagged in REPORT.md): two defensible targets exist — the
Archaeology subsection's 'Archaeological discovery: lost Mayan city
uncovered in Mexican jungle using LiDAR' (which the site's own search
ranks first) and the newer science story 'First writing may be 40,000
years earlier than thought'. Both are accepted; the graded facts follow
the story the agent opened. Checks: opened one of the two; the answer
states that story's findings.

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

CONTEXT_PAGES = ["/news/science"]
CONTEXT_SEARCHES = ["archaeolog", "archaeological discovery"]
GROUND_TRUTH = [
 {
  "slug": "archaeological-discovery-lost-mayan-city-uncovered-in-mexican-jungle-u",
  "title": "Archaeological discovery: lost Mayan city uncovered in Mexican jungle using LiDAR",
  "facts": [
   [
    "mayan",
    "maya"
   ],
   [
    "mexico"
   ],
   [
    "lidar",
    "laser"
   ],
   [
    "jungle"
   ],
   [
    "plazas",
    "pyramids",
    "roads",
    "lost city"
   ]
  ],
  "min_facts": 3
 },
 {
  "slug": "cvgknj7yyv2o",
  "title": "First writing may be 40,000 years earlier than thought",
  "facts": [
   [
    "writing"
   ],
   [
    "40,000",
    "40000",
    "40 000",
    "forty thousand",
    "tens of thousands"
   ],
   [
    "germany",
    "stone age"
   ],
   [
    "mammoth",
    "tusk",
    "ivory"
   ],
   [
    "cave",
    "caves"
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
    run("BBC News--27", body)
