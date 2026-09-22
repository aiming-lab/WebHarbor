#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--28.

The Market Data section: which company the data comes from.

The Market Data section (/news/market_data) is powered by Morningstar,
as stated in the section's own explainer and in every market-data
story's byline note. Checks: opened the Market Data section or its
explainer story; the answer names Morningstar.

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

CONTEXT_PAGES = ["/news/market_data", "/news/business"]
CONTEXT_SEARCHES = ["market data"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = (opened_article(traj, ["market-data-live-prices"])
              or opened_page(traj, "/news/market_data"))
    j.check("browsed_market_data", bool(opened),
            "opened the Market Data section or its 'live prices' explainer")
    j.check("answer_names_data_provider",
            mentions_group(ans, ["morningstar"]),
            "the market data feed is provided by Morningstar")

if __name__ == "__main__":
    run("BBC News--28", body)
