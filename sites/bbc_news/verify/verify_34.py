#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--34.

The SpeciaList section in Travel: which cities are mentioned.

Travel's SpeciaList series holds 'The SpeciaList: three coastal towns in
Portugal for autumn' (Porto, Nazaré, Sagres) and 'The SpeciaList: five
cities to visit in 2026, from Lisbon to Kyoto' (Lisbon, Kyoto, Mexico
City, Tbilisi, Cape Town). Either story satisfies the task. Checks:
opened one of the two; the answer names at least two of its cities.

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

CONTEXT_PAGES = ["/news/travel", "/news/the_specialist"]
CONTEXT_SEARCHES = ["specialist"]
GROUND_TRUTH = [
 {
  "slug": "travel-the-specialist-three-coastal-towns-in-portugal-for-autumn",
  "title": "The SpeciaList: three coastal towns in Portugal for autumn",
  "facts": [],
  "min_facts": 0,
  "cities": [
   [
    "porto"
   ],
   [
    "nazare",
    "nazaré"
   ],
   [
    "sagres"
   ]
  ]
 },
 {
  "slug": "the-specialist-five-cities-to-visit-in-2026-from-lisbon-to-kyoto",
  "title": "The SpeciaList: five cities to visit in 2026, from Lisbon to Kyoto",
  "facts": [],
  "min_facts": 0,
  "cities": [
   [
    "lisbon"
   ],
   [
    "kyoto"
   ],
   [
    "mexico city"
   ],
   [
    "tbilisi"
   ],
   [
    "cape town"
   ]
  ]
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
    best = None
    for g in GROUND_TRUTH:
        hits = group_hits(ans, g["cities"])
        if best is None or hits > best[0]:
            best = (hits, g)
    j.check("answer_names_cities", best is not None and best[0] >= 2,
            f"cities hit={best[0] if best else 0}/{len(best[1]['cities']) if best else 0} "
            f"(need 2) for {best[1]['title']!r}" if best else "no SpeciaList entry")

if __name__ == "__main__":
    run("BBC News--34", body)
