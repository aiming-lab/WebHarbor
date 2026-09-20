#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--19.

Athletics calendar: the date of the next earliest game.

AUDIT NOTE (flagged in REPORT.md): the four Athletics calendar stories
disagree — the Doha story self-describes as 'the next earliest fixture
(10 May 2026)' while the later-published London Marathon story is dated
26 April 2026. Both readings are accepted: the earliest upcoming event
across the calendar (London Marathon, 26 April) or the Doha fixture the
mirror itself labels next-earliest (10 May). Checks: opened at least one
Athletics calendar story; the answer pairs an event with its date.

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

CONTEXT_PAGES = ["/news/athletics", "/news/sport"]
CONTEXT_SEARCHES = ["athletics", "athletics calendar"]
GROUND_TRUTH = [
 {
  "slug": "athletics-calendar-diamond-league-rome-golden-gala-returns-june-6",
  "title": "Athletics calendar: Diamond League Rome Golden Gala returns June 6",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "athletics-calendar-london-marathon-2026-elite-field-announced",
  "title": "Athletics calendar: London Marathon 2026 elite field announced",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "athletics-calendar-european-indoor-championships-istanbul-preview",
  "title": "Athletics calendar: European Indoor Championships Istanbul preview",
  "facts": [],
  "min_facts": 0
 },
 {
  "slug": "athletics-calendar-diamond-league-doha-opens-the-2026-season",
  "title": "Athletics calendar: Diamond League Doha opens the 2026 season",
  "facts": [],
  "min_facts": 0
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
    london = (mentions_group(ans, ["london marathon"])
              and mentions_date(ans, 26, "April", 2026))
    doha = (mentions_group(ans, ["doha"])
            and mentions_date(ans, 10, "May", 2026))
    j.check("answer_states_next_earliest_game", london or doha,
            "accepted: London Marathon on 26 April 2026, or the Diamond League "
            "Doha fixture on 10 May 2026")

if __name__ == "__main__":
    run("BBC News--19", body)
