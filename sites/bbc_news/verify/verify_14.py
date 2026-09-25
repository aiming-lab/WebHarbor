#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--14.

Tech industry layoffs' impact on the global economy: key points, author
and publication date.

The Tech Layoffs subsection lead is 'Tech layoffs ripple through global
economy as 250,000 jobs cut' (Natalie Sherman, 14 Apr 2026). Checks:
opened that article; the answer states the 250,000 figure, the knock-on
effects, the author and the publication date.

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

CONTEXT_PAGES = ["/news/business"]
CONTEXT_SEARCHES = ["tech layoffs", "layoffs"]
GROUND_TRUTH = {
 "facts": [
  [
   "supply chain"
  ],
  [
   "commercial property"
  ],
  [
   "consumer spending"
  ],
  [
   "big tech",
   "startups",
   "startups slash"
  ]
 ]
}


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["tech-layoffs-ripple-through-global-economy"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_states_job_count",
            mentions_number(ans, 250000) or mentions_group(
                ans, ["quarter of a million"]),
            "250,000 technology jobs have been cut")
    j.check("answer_states_economic_impact",
            group_hits(ans, GROUND_TRUTH["facts"]) >= 1,
            "knock-on effects: supply chains, commercial property, consumer spending")
    j.check("answer_names_author", mentions_group(ans, ["natalie sherman"]),
            "the article's author is Natalie Sherman")
    j.check("answer_states_publication_date", mentions_date(ans, 14, "April", 2026),
            "the article was published 14 April 2026")

if __name__ == "__main__":
    run("BBC News--14", body)
