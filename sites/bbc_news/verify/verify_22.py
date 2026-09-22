#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--22.

Current top business story and its economic implications.

The Business section (/news/business) lead is 'Market Data: FTSE 100
closes at record high as banks and miners lead' (15 Apr 2026). Checks:
opened the Business section (or a business search) and that article;
the answer states the FTSE 100 record and the banks/miners driver.

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

CONTEXT_PAGES = ["/news/business", "/latest"]
CONTEXT_SEARCHES = ["business"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["market-data-ftse-100-closes-at-record-high"])
    context = (opened_page(traj, "/news/business") or searched(traj, "business")
               or opened_page(traj, "/latest"))
    j.check("grounded_on_site", bool(opened) or context,
            f"opened={opened}; the top story is identified from /news/business, "
            f"a business search, or /latest")
    j.check("answer_states_top_story",
            mentions_group(ans, ["ftse 100"]) and mentions_group(
                ans, ["record high", "all-time high", "new record"]),
            "top story: the FTSE 100 closed at a record high")
    j.check("answer_states_economic_implications",
            group_hits(ans, [["banks", "hsbc", "barclays", "lloyds"],
                            ["miners", "mining"]]) >= 1,
            "financial and mining stocks drove the gains")

if __name__ == "__main__":
    run("BBC News--22", body)
