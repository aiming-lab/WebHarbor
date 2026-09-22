#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--10.

Main headlines covering the UK's plan to tackle climate change.

The UK section's Climate Policy subsection carries the plan coverage:
£30bn net-zero plan, 2035 petrol-car ban, 'not yet credible' watchdog
verdict, £10bn insulation scheme, Parliament approving the updated Net
Zero Strategy, and the £500m peatland programme. Checks: opened at least
two of the six articles; the answer covers at least three of the plan
topics.

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

CONTEXT_PAGES = ["/news/uk"]
CONTEXT_SEARCHES = ["climate change", "net zero", "climate plan"]
GROUND_TRUTH = [
 {
  "slug": "uk-unveils-30bn-plan-to-hit-net-zero-by-2050",
  "title": "UK unveils £30bn plan to hit net zero by 2050",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "uk-government-to-ban-new-petrol-car-sales-from-2035-in-updated-plan",
  "title": "UK government to ban new petrol car sales from 2035 in updated plan",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "uk-s-climate-watchdog-says-plan-not-yet-credible",
  "title": "UK's climate watchdog says plan 'not yet credible'",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "uk-launches-10bn-green-home-insulation-scheme-as-part-of-climate-plan",
  "title": "UK launches £10bn green home insulation scheme as part of climate plan",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "uk-plan-to-tackle-climate-change-parliament-approves-updated-net-zero-",
  "title": "UK plan to tackle climate change: Parliament approves updated Net Zero Strategy",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "uk-wide-peatland-restoration-programme-to-lock-away-millions-of-tonnes",
  "title": "UK-wide peatland restoration programme to lock away millions of tonnes of carbon",
  "facts": [],
  "min_facts": 0
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
PLAN_TOPICS = [
    ["30bn", "£30bn", "net zero plan"],
    ["2035", "petrol", "diesel"],
    ["not yet credible", "climate change committee", "watchdog"],
    ["10bn", "insulation", "7,500"],
    ["net zero strategy", "parliament", "mps"],
    ["peatland", "500m", "carbon"],
]


def body(j, traj, ans):
    slugs = [g["slug"] for g in GROUND_TRUTH]
    opened = opened_article(traj, slugs)
    j.check("grounded_in_plan_coverage",
            len(opened) >= 2 or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    hits = group_hits(ans, PLAN_TOPICS)
    j.check("answer_covers_plan_headlines", hits >= 3,
            f"plan topics hit={hits}/6 (need 3)")

if __name__ == "__main__":
    run("BBC News--10", body)
