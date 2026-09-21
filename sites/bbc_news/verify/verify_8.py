#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--8.

Economic implications of the UK's latest trade deal and its publication
date.

The Trade subsection's same-day cluster (14 Apr 2026) is anchored on the
UK-India deal — 'UK signs post-Brexit trade deal with India worth £20bn a
year' and its follow-up 'Economists warn UK–India trade deal benefits may
take years to materialise'. Either article satisfies the task; both were
published 14 Apr 2026. Checks: opened one of the two; answer states the
India deal facts and the 14 April 2026 publication date.

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

CONTEXT_PAGES = ["/news/business"]
CONTEXT_SEARCHES = ["trade deal", "trade"]
GROUND_TRUTH = [
 {
  "slug": "uk-signs-post-brexit-trade-deal-with-india-worth-20bn-a-year",
  "title": "UK signs post-Brexit trade deal with India worth £20bn a year",
  "facts": [
   [
    "india"
   ],
   [
    "£20bn",
    "20bn",
    "20 billion"
   ],
   [
    "free trade",
    "trade deal",
    "trade agreement"
   ],
   [
    "whisky",
    "cars",
    "textiles",
    "tariff"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "economists-warn-uk-india-trade-deal-benefits-may-take-years-to-materia",
  "title": "Economists warn UK–India trade deal benefits may take years to materialise",
  "facts": [
   [
    "india"
   ],
   [
    "years to materialise",
    "take years",
    "years"
   ],
   [
    "gdp",
    "implementation",
    "economists",
    "economic gains"
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
    matched = [g for g in GROUND_TRUTH if group_hits(ans, g["facts"]) >= g["min_facts"]]
    j.check("answer_matches_india_deal_coverage", bool(matched),
            f"matched={[g['title'] for g in matched]}")
    j.check("answer_states_publication_date", mentions_date(ans, 14, "April", 2026),
            "the article was published 14 April 2026")

if __name__ == "__main__":
    run("BBC News--8", body)
