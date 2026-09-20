#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--41.

Golf leaderboard in Women's Majors: which country has the most players
in the top 20, and the best-placed Australian player and their position.

The Women's Majors leaderboard story: the United States fields the most
players in the top 20; Australia has four, with Minjee Lee best-placed
at 1st (leads at -6 through 54 holes at Pine Needles). Checks: opened
that story; the answer states the US count, Minjee Lee and her 1st place.

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
CONTEXT_SEARCHES = ["women's majors", "womens majors", "golf"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["women-s-majors-golf-leaderboard"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_states_top_country",
            mentions_group(ans, ["united states", "u s", "usa", "america"]),
            "the United States has the most players in the top 20")
    j.check("answer_states_best_australian",
            mentions_group(ans, ["minjee lee"]),
            "Minjee Lee is the best-placed Australian player")
    j.check("answer_states_position",
            mentions_group(ans, ["1st", "first", "leads", "leader", "number 1",
                                 "top of the leaderboard"]),
            "Minjee Lee is in 1st place")

if __name__ == "__main__":
    run("BBC News--41", body)
