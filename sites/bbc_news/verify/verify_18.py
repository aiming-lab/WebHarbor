#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--18.

BBC News Audio: the best podcasts for 2023 — list two of them.

'Best podcasts of 2023: BBC Sounds picks the year's must-listens' lists
The Rest Is History, Global News Podcast, The Infinite Monkey Cage,
Americast, Newscast and The Coming Storm. Checks: opened that article;
the answer names at least two of the six.

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

CONTEXT_PAGES = ["/news/audio", "/news/podcasts"]
CONTEXT_SEARCHES = ["podcast", "best podcasts"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
PODCASTS = [["the rest is history"], ["global news podcast"],
            ["the infinite monkey cage"], ["americast"], ["newscast"],
            ["the coming storm"]]


def body(j, traj, ans):
    opened = opened_article(traj, ["best-podcasts-of-2023"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    hits = group_hits(ans, PODCASTS)
    j.check("answer_lists_two_podcasts", hits >= 2,
            f"podcasts named={hits}/6 (need 2)")

if __name__ == "__main__":
    run("BBC News--18", body)
