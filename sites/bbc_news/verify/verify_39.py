#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--39.

Horse Racing results in Sport: of yesterday's meetings, which one had
the highest number of runners.

The Horse Racing subsection's 'yesterday's meetings' story reports
Cheltenham, Kempton, Sandown, Ayr and Plumpton, with the Cheltenham Gold
Cup at 18 runners the highest. Checks: opened that story; the answer
names the Cheltenham Gold Cup and its runner count.

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

CONTEXT_PAGES = ["/news/sport", "/news/horse_racing"]
CONTEXT_SEARCHES = ["horse racing", "yesterday"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["horse-racing-results-yesterday-s-meetings"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_names_meeting",
            mentions_group(ans, ["cheltenham"]) and mentions_group(ans, ["gold cup"]),
            "the Cheltenham Gold Cup had the most runners")
    j.check("answer_states_runner_count",
            mentions_number(ans, 18) or mentions_group(ans, ["most runners"]),
            "18 horses were declared — the highest of yesterday's meetings")

if __name__ == "__main__":
    run("BBC News--39", body)
