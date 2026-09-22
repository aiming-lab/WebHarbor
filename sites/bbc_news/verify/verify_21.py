#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--21.

Top headline in the World News section and the region it relates to.

The World section (/news/world) lead is 'Middle East crisis: Gaza
ceasefire talks enter critical phase in Cairo' (14 Apr 2026) — the
region is the Middle East (Gaza/Cairo). Checks: opened the World section
(or a world search) and that article; the answer names the headline's
facts and the region.

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

CONTEXT_PAGES = ["/news/world", "/latest"]
CONTEXT_SEARCHES = ["world"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["middle-east-crisis-gaza-ceasefire-talks-enter"])
    context = (opened_page(traj, "/news/world") or searched(traj, "world")
               or opened_page(traj, "/latest"))
    j.check("grounded_on_site", bool(opened) or context,
            f"opened={opened}; the top story is identified from /news/world, a "
            f"world search, or /latest")
    j.check("answer_states_headline_facts",
            group_hits(ans, [["gaza"], ["ceasefire"], ["cairo"], ["middle east"]]) >= 3,
            "top headline: Gaza ceasefire talks in a critical phase in Cairo "
            "(Middle East)")
    j.check("answer_states_region",
            mentions_group(ans, ["middle east", "gaza", "cairo", "israel"]),
            "the story relates to the Middle East region")

if __name__ == "__main__":
    run("BBC News--21", body)
