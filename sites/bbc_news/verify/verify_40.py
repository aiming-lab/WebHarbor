#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--40.

A recent story about people being injured or killed in wars.

The War & Conflict section's casualty stories are all defensible picks;
the graded facts follow the story the agent opened. Checks: opened one
of the ten; the answer states that story's casualty facts.

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

CONTEXT_PAGES = ["/news/war", "/news/world"]
CONTEXT_SEARCHES = ["war", "casualties", "killed"]
GROUND_TRUTH = [
 {
  "slug": "ukraine-war-civilian-casualties-rise-in-kharkiv-oblast-un-monitor-says",
  "title": "Ukraine war: civilian casualties rise in Kharkiv oblast, UN monitor says",
  "facts": [
   [
    "kharkiv"
   ],
   [
    "civilian casualties",
    "civilian"
   ],
   [
    "17%",
    "17 per cent"
   ],
   [
    "412",
    "78 killed",
    "un monitor"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "gaza-war-mothers-and-children-among-latest-victims-of-strike-on-rafah",
  "title": "Gaza war: mothers and children among latest victims of strike on Rafah",
  "facts": [
   [
    "rafah"
   ],
   [
    "killed",
    "victims"
   ],
   [
    "12 children",
    "children",
    "mothers"
   ],
   [
    "23"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "sudan-civil-war-famine-declared-in-el-fasher-as-fighting-blocks-aid",
  "title": "Sudan civil war: famine declared in El Fasher as fighting blocks aid",
  "facts": [
   [
    "el fasher",
    "darfur",
    "sudan"
   ],
   [
    "famine"
   ],
   [
    "starvation",
    "aid",
    "60,000",
    "90,000"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "yemen-war-hospital-in-sanaa-hit-in-overnight-airstrike-20-killed",
  "title": "Yemen war: hospital in Sanaa hit in overnight airstrike, 20 killed",
  "facts": [
   [
    "sanaa",
    "yemen"
   ],
   [
    "hospital"
   ],
   [
    "20 killed",
    "20 people",
    "airstrike"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "gaza-war-hospital-in-rafah-overwhelmed-as-casualties-mount",
  "title": "Gaza war: hospital in Rafah overwhelmed as casualties mount",
  "facts": [
   [
    "rafah",
    "gaza"
   ],
   [
    "hospital"
   ],
   [
    "casualties",
    "overwhelmed"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "ukraine-war-front-line-reshaped-after-latest-russian-offensive",
  "title": "Ukraine war: front line reshaped after latest Russian offensive",
  "facts": [
   [
    "ukraine",
    "kharkiv"
   ],
   [
    "russian offensive",
    "russia"
   ],
   [
    "evacuated",
    "front line"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "middle-east-war-un-warns-of-famine-risk-in-gaza",
  "title": "Middle East war: UN warns of famine risk in Gaza",
  "facts": [
   [
    "gaza"
   ],
   [
    "famine"
   ],
   [
    "un"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "sudan-civil-war-bbc-reports-from-darfur-as-fighting-escalates",
  "title": "Sudan civil war: BBC reports from Darfur as fighting escalates",
  "facts": [
   [
    "darfur",
    "sudan"
   ],
   [
    "civil war"
   ],
   [
    "displaced",
    "millions",
    "humanitarian"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "yemen-war-cross-border-strikes-continue-despite-ceasefire-talks",
  "title": "Yemen war: cross-border strikes continue despite ceasefire talks",
  "facts": [
   [
    "yemen"
   ],
   [
    "strikes"
   ],
   [
    "ceasefire"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "myanmar-war-rebel-alliance-claims-control-of-key-border-town",
  "title": "Myanmar war: rebel alliance claims control of key border town",
  "facts": [
   [
    "myanmar"
   ],
   [
    "rebel"
   ],
   [
    "border town"
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
    run("BBC News--40", body)
