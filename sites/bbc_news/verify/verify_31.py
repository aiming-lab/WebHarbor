#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--31.

Sports section: the result of the most recent Manchester United match.

The Football subsection's only match report is 'Manchester United 3-1
Liverpool: Red Devils win Old Trafford derby' (14 Apr 2026). Checks:
opened that report; the answer states the 3-1 win over Liverpool at Old
Trafford.

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
CONTEXT_SEARCHES = ["manchester united"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["manchester-united-3-1-liverpool"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_states_result",
            mentions_group(ans, ["3-1", "3 1", "won 3-1", "beat liverpool 3"]),
            "Manchester United beat Liverpool 3-1")
    j.check("answer_names_teams",
            mentions_group(ans, ["manchester united"])
            and mentions_group(ans, ["liverpool"]),
            "Manchester United vs Liverpool")
    j.check("answer_states_venue", mentions_group(ans, ["old trafford"]),
            "the match was played at Old Trafford")

if __name__ == "__main__":
    run("BBC News--31", body)
