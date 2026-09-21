#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--3.

DP World Tour leaderboard in the Sport section: name of the most recent
tournament and how many teams have a Total of -10 strokes.

The Golf section (/news/golf) lead is the Hero Indian Open leaderboard
article: Jon Rahm leads on -14, five players tied at -10. Checks: opened
the leaderboard article; the answer names the Hero Indian Open and states
the -10 count as 5/five.

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

CONTEXT_PAGES = ["/news/golf", "/news/sport"]
CONTEXT_SEARCHES = ["dp world tour", "golf", "leaderboard"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["dp-world-tour-hero-indian-open-leaderboard-rahm-leads-on-14"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_names_tournament", mentions_group(ans, ["hero indian open", "indian open"]),
            "the most recent DP World Tour tournament is the Hero Indian Open")
    five = mentions_number(ans, 5) or " five " in f" {norm(ans)} "
    j.check("answer_counts_minus10_field", five,
            "five players are tied at -10 on the leaderboard")

if __name__ == "__main__":
    run("BBC News--3", body)
