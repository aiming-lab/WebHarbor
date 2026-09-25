#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--36.

Africa news section in World: what topics most of the recent articles
are about.

The Africa section (/news/africa) carries the Kenya election, Horn of
Africa drought, Nigeria fintech, South Africa power cuts,
Ethiopia-Eritrea peace talks, Ghana digital currency stories (plus the
Sudan famine and Morocco/food pieces). Checks: browsed the Africa
section and opened at least one of its stories; the answer ties at
least three of the section's subjects together with an overall topic.

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

CONTEXT_PAGES = ["/news/africa", "/news/world"]
CONTEXT_SEARCHES = ["africa"]
GROUND_TRUTH = [
 {
  "slug": "africa-kenya-election-result-sparks-street-celebrations",
  "title": "Africa: Kenya election result sparks street celebrations in Nairobi",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "africa-drought-grips-the-horn-of-africa-as-un-appeals-f",
  "title": "Africa: drought grips the Horn of Africa as UN appeals for aid",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "africa-nigeria-s-fintech-boom-draws-record-investment",
  "title": "Africa: Nigeria's fintech boom draws record investment",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "africa-south-africa-s-power-cuts-ease-after-record-wind",
  "title": "Africa: South Africa's power cuts ease after record wind generation",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "africa-ethiopia-eritrea-peace-talks-resume-amid-renewed",
  "title": "Africa: Ethiopia-Eritrea peace talks resume amid renewed border tensions",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "africa-ghana-launches-continent-wide-digital-currency-p",
  "title": "Africa: Ghana launches continent-wide digital currency pilot",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "sudan-civil-war-famine-declared-in-el-fasher-as-fighting-blocks-aid",
  "title": "Sudan civil war: famine declared in El Fasher as fighting blocks aid",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "travel-morocco-s-mountain-food-tagines-and-amlou-in-the-atlas",
  "title": "Morocco's mountain food: tagines and amlou in the Atlas",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "natural-wonders-namibia-s-fairy-circles-new-theory-links-the",
  "title": "Natural wonders: Namibia's fairy circles — new theory links them to termites",
  "facts": [],
  "min_facts": 0
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
SUBJECTS = [
    ["kenya", "election"], ["drought", "horn of africa"],
    ["nigeria", "fintech"], ["south africa", "power cuts", "wind generation"],
    ["ethiopia", "eritrea", "peace talks"], ["ghana", "digital currency"],
    ["sudan", "famine", "darfur"], ["morocco", "tagine", "atlas"],
    ["namibia", "fairy circles"],
]
TOPIC_WORDS = ["politic", "election", "conflict", "war", "econom", "energ",
               "technolog", "digital", "development", "humanitarian", "aid"]


def body(j, traj, ans):
    opened = opened_article(traj, [g["slug"] for g in GROUND_TRUTH])
    j.check("browsed_africa_section",
            opened_page(traj, "/news/africa") or searched(traj, "africa"),
            f"the task is about the Africa news section in World "
            f"(opened={opened})")
    subj = group_hits(ans, SUBJECTS)
    j.check("answer_covers_section_subjects", subj >= 3,
            f"section subjects hit={subj}/9 (need 3)")
    low = norm(ans)
    j.check("answer_states_overall_topic",
            any(w in low for w in TOPIC_WORDS),
            "the answer characterizes what most of the coverage is about")

if __name__ == "__main__":
    run("BBC News--36", body)
