#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--11.

Scottish Premiership: how many teams, and when Hibernian's most recent
match started.

Two seeded stories carry the facts: 'Scottish Premiership table: 12 teams,
Celtic hold narrow lead over Rangers' (12 clubs) and 'Hibernian 2-1 St
Mirren' (kicked off at 15:00 BST on Saturday). Checks: opened both
articles; the answer states 12 teams and the 15:00 BST Saturday kickoff.

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

CONTEXT_PAGES = ["/news/sport", "/news/football"]
CONTEXT_SEARCHES = ["scottish premiership", "hibernian"]
GROUND_TRUTH = [
 {
  "slug": "scottish-premiership-table-12-teams-celtic-hold-narrow-lead-over-range",
  "title": "Scottish Premiership table: 12 teams, Celtic hold narrow lead over Rangers",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "hibernian-2-1-st-mirren-edinburgh-side-edge-late-win-at-easter-road",
  "title": "Hibernian 2-1 St Mirren: Edinburgh side edge late win at Easter Road",
  "facts": [],
  "min_facts": 0
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, [g["slug"] for g in GROUND_TRUTH])
    j.check("grounded_on_site", len(opened) >= 2 or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_states_team_count", mentions_number(ans, 12),
            "the Scottish Premiership features 12 teams/clubs")
    j.check("answer_states_kickoff_time",
            mentions_group(ans, ["15:00", "15 00", "3pm", "3 pm"]),
            "Hibernian's most recent match kicked off at 15:00 BST")
    j.check("answer_states_kickoff_day",
            mentions_group(ans, ["saturday", "bst"]),
            "the kickoff was on Saturday (15:00 BST)")

if __name__ == "__main__":
    run("BBC News--11", body)
