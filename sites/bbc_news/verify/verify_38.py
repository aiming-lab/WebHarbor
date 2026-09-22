#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--38.

Weather section: the storm news — where and when the severe weather
occurred.

The Weather section's newest storm stories are 'Weather: Storm Isha
brings severe winds and flooding to western Scotland on Sunday' and
'Weather: Storm Kathleen batters Ireland and western Scotland'. Either
is 'the storm'; the where/when facts follow the story the agent opened.
Checks: opened one of the two; the answer states that storm's location
and time.

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

CONTEXT_PAGES = ["/news/weather"]
CONTEXT_SEARCHES = ["storm", "weather"]
GROUND_TRUTH = [
 {
  "slug": "weather-storm-isha-brings-severe-winds-and-flooding-to-western-scotlan",
  "title": "Weather: Storm Isha brings severe winds and flooding to western Scotland on Sunday",
  "facts": [
   [
    "storm isha",
    "isha"
   ],
   [
    "western scotland",
    "scotland"
   ],
   [
    "sunday"
   ],
   [
    "red warning",
    "100 mph",
    "flooding"
   ]
  ],
  "min_facts": 3
 },
 {
  "slug": "weather-storm-kathleen-batters-ireland-and-western-scotland",
  "title": "Weather: Storm Kathleen batters Ireland and western Scotland",
  "facts": [
   [
    "storm kathleen",
    "kathleen"
   ],
   [
    "ireland"
   ],
   [
    "western scotland",
    "scotland"
   ],
   [
    "overnight",
    "03:00",
    "3 am",
    "amber"
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
    run("BBC News--38", body)
