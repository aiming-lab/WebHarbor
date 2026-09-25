#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--6.

Top story in the technology section.

The Technology section (/news/technology) lead — its newest article — is
'Artificial Intelligence: EU AI Act — the rules coming into force in
2026' (15 Apr 2026). Checks: opened the Technology section page and that
article; the answer identifies the EU AI Act story.

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

CONTEXT_PAGES = ["/news/technology", "/latest"]
CONTEXT_SEARCHES = ["technology", "tech"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["artificial-intelligence-eu-ai-act-the-rules-coming"])
    context = (opened_page(traj, "/news/technology")
               or any(searched(traj, t) for t in ["technology", "tech"])
               or opened_page(traj, "/latest"))
    j.check("grounded_on_site", bool(opened) or context,
            f"opened={opened}; the top story is identified from the Technology "
            f"section (/news/technology), a tech search, or /latest")
    j.check("answer_names_top_story",
            mentions_group(ans, ["eu ai act", "ai act"]) and mentions_number(ans, 2026),
            "top story: EU AI Act rules coming into force in 2026")

if __name__ == "__main__":
    run("BBC News--6", body)
