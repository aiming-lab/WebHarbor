#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--17.

How many War related sections are currently in BBC News.

AUDIT NOTE (flagged in REPORT.md): this task is ill-posed on the
mirror — no page displays a count of 'war related sections'. Four
readings are derivable from the mirror: 1 (the single War & Conflict
section), 5 (the war subsections behind it), 6 (the distinct
conflicts its headlines cover), and 9 (the stories listed on
/news/war). The contract requires the agent to have browsed the war
coverage and to state one of those four counts; any other count
(e.g. 3 or 8) is a FAIL. Checks: browsed /news/war or a war story;
the answer states a defensible count.

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
CONTEXT_SEARCHES = ["war"]
GROUND_TRUTH = [
 {
  "slug": "ukraine-war-civilian-casualties-rise-in-kharkiv-oblast-un-monitor-says",
  "title": "Ukraine war: civilian casualties rise in Kharkiv oblast, UN monitor says",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "gaza-war-mothers-and-children-among-latest-victims-of-strike-on-rafah",
  "title": "Gaza war: mothers and children among latest victims of strike on Rafah",
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
  "slug": "yemen-war-hospital-in-sanaa-hit-in-overnight-airstrike-20-killed",
  "title": "Yemen war: hospital in Sanaa hit in overnight airstrike, 20 killed",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "ukraine-war-front-line-reshaped-after-latest-russian-offensive",
  "title": "Ukraine war: front line reshaped after latest Russian offensive",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "middle-east-war-un-warns-of-famine-risk-in-gaza",
  "title": "Middle East war: UN warns of famine risk in Gaza",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "sudan-civil-war-bbc-reports-from-darfur-as-fighting-escalates",
  "title": "Sudan civil war: BBC reports from Darfur as fighting escalates",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "yemen-war-cross-border-strikes-continue-despite-ceasefire-talks",
  "title": "Yemen war: cross-border strikes continue despite ceasefire talks",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "myanmar-war-rebel-alliance-claims-control-of-key-border-town",
  "title": "Myanmar war: rebel alliance claims control of key border town",
  "facts": [],
  "min_facts": 0
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
CONFLICT_NAMES = [["ukraine"], ["gaza"], ["sudan"], ["yemen"],
                  ["myanmar"], ["middle east"]]


def body(j, traj, ans):
    nav = (opened_page(traj, "/news/war")
           or bool(opened_article(traj, [g["slug"] for g in GROUND_TRUTH]))
           or searched(traj, "war"))
    j.check("browsed_war_coverage", nav,
            "the count must come from the mirror's war coverage")
    one = mentions_number(ans, 1) or " one " in f" {norm(ans)} "
    five = mentions_number(ans, 5) or " five " in f" {norm(ans)} "
    six = mentions_number(ans, 6) or " six " in f" {norm(ans)} "
    nine = mentions_number(ans, 9) or " nine " in f" {norm(ans)} "
    count_ok = one or five or six or nine
    j.check("answer_states_defensible_count", count_ok,
            "accepted counts: 1 (the War & Conflict section), 5 (war "
            "subsections), 6 (distinct conflicts covered), or 9 (stories "
            "listed in the War & Conflict section)")

if __name__ == "__main__":
    run("BBC News--17", body)
