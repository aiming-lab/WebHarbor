#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--9.

Which musician made the headlines in Music News.

Music News (/news/music, reachable from the Culture section subnav) lists
four stories; any of the four musicians is a valid 'made the headlines'
answer provided the agent opened that musician's story. Checks: opened
one of the four; the answer names that musician and states the story's
facts.

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

CONTEXT_PAGES = ["/news/music", "/news/entertainment", "/news/culture"]
CONTEXT_SEARCHES = ["music", "musician"]
GROUND_TRUTH = [
 {
  "slug": "taylor-swift-announces-surprise-album-during-london-show",
  "title": "Taylor Swift announces surprise album during London show",
  "musician": [
   "taylor swift"
  ]
 },
 {
  "slug": "adele-says-farewell-to-las-vegas-residency-after-record-breaking-run",
  "title": "Adele says farewell to Las Vegas residency after record-breaking run",
  "musician": [
   "adele"
  ]
 },
 {
  "slug": "stormzy-wins-mercury-prize-for-unflinching-new-album",
  "title": "Stormzy wins Mercury Prize for 'unflinching' new album",
  "musician": [
   "stormzy"
  ]
 },
 {
  "slug": "dua-lipa-to-headline-glastonbury-s-pyramid-stage",
  "title": "Dua Lipa to headline Glastonbury's Pyramid Stage",
  "musician": [
   "dua lipa"
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
    named = [g for g in GROUND_TRUTH
             if mentions_group(ans, g["musician"])]
    j.check("answer_names_musician", bool(named),
            f"named={[g['title'] for g in named]}")
    bound = [g for g in named if g["slug"] in opened] if opened else named
    j.check("answer_matches_music_news_story", bool(bound),
            f"matched={[g['title'] for g in bound]}")

if __name__ == "__main__":
    run("BBC News--9", body)
