#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--12.

Find a picture in the travel section that contains food; name the food
and its region.

The travel section's food stories (audited): pintxos in Spain's San
Sebastián/Basque Country, tagines and amlou in Morocco's Atlas, arancini
in Sicily/Palermo, and banh mi in Vietnam. The hero images of the banh mi
and arancini stories depict food; the pintxos/tagines heroes are scenery
(flagged in REPORT.md) — the graded facts are the on-page food names and
regions. Checks: opened one of the four; the answer names that food and
its region.

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

CONTEXT_PAGES = ["/news/travel"]
CONTEXT_SEARCHES = ["food", "travel"]
GROUND_TRUTH = [
 {
  "slug": "travel-spain-san-sebastian-where-to-eat-pintxos-on-a-budget",
  "title": "Spain's San Sebastián: where to eat pintxos on a budget",
  "facts": [
   [
    "pintxos",
    "pintxo"
   ],
   [
    "basque",
    "san sebastian",
    "spain"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "travel-morocco-s-mountain-food-tagines-and-amlou-in-the-atlas",
  "title": "Morocco's mountain food: tagines and amlou in the Atlas",
  "facts": [
   [
    "tagine",
    "tagines",
    "amlou"
   ],
   [
    "atlas",
    "morocco",
    "moroccan",
    "imlil",
    "berber"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "a-taste-of-sicily-where-to-find-the-perfect-arancini-in-palermo",
  "title": "A taste of Sicily: where to find the perfect arancini in Palermo",
  "facts": [
   [
    "arancini"
   ],
   [
    "sicily",
    "sicilian",
    "palermo"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "vietnam-s-banh-mi-the-sandwich-that-tells-a-country-s-story",
  "title": "Vietnam's banh mi: the sandwich that tells a country's story",
  "facts": [
   [
    "banh mi"
   ],
   [
    "vietnam",
    "vietnamese",
    "saigon"
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
    run("BBC News--12", body)
