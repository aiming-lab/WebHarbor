#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--33.

World News section: the latest war situations of the Middle East.

The World section's Middle East subsection carries two 14 Apr 2026 war
situation stories — 'Middle East crisis: Gaza ceasefire talks enter
critical phase in Cairo' and 'World News: latest war situation in the
Middle East as fighting spreads to Lebanon border'. Either satisfies
'latest war situation'. Checks: opened one of the two; the answer states
that story's facts.

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

CONTEXT_PAGES = ["/news/world"]
CONTEXT_SEARCHES = ["middle east", "war"]
GROUND_TRUTH = [
 {
  "slug": "middle-east-crisis-gaza-ceasefire-talks-enter-critical-phase-in-cairo",
  "title": "Middle East crisis: Gaza ceasefire talks enter critical phase in Cairo",
  "facts": [
   [
    "gaza"
   ],
   [
    "ceasefire"
   ],
   [
    "cairo"
   ],
   [
    "hostages"
   ],
   [
    "israel",
    "hamas"
   ],
   [
    "mediators"
   ]
  ],
  "min_facts": 3
 },
 {
  "slug": "world-news-latest-war-situation-in-the-middle-east-as-fighting-spreads",
  "title": "World News: latest war situation in the Middle East as fighting spreads to Lebanon border",
  "facts": [
   [
    "middle east"
   ],
   [
    "lebanon",
    "lebanon border"
   ],
   [
    "fighting"
   ],
   [
    "heavy fire",
    "worsened",
    "worsens"
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
    run("BBC News--33", body)
