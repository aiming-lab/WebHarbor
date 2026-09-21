#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--16.

Most recent development or update in Brexit negotiations, key points and
stated impacts on European economies.

The Brexit subsection's newest story is 'Brexit deal update: UK and EU
agree fresh talks on Northern Ireland trade' (23 Mar 2026): reopening
negotiations on post-Brexit trade arrangements for Northern Ireland to
smooth paperwork for hauliers. Checks: opened that article; the answer
states the Northern Ireland talks and their aim.

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
CONTEXT_SEARCHES = ["brexit"]
GROUND_TRUTH = [
 {
  "slug": "brexit-deal-update-uk-and-eu-agree-fresh-talks-on-northern-ireland-tra",
  "title": "Brexit deal update: UK and EU agree fresh talks on Northern Ireland trade",
  "facts": [
   [
    "northern ireland"
   ],
   [
    "fresh talks",
    "reopen",
    "negotiations"
   ],
   [
    "hauliers",
    "paperwork",
    "trade arrangements"
   ],
   [
    "uk and eu",
    "uk-eu"
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
    run("BBC News--16", body)
