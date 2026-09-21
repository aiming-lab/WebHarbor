#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--37.

Culture section: the latest book review — the book's title and author.

The Culture section's newest book review is "Book review: 'The
Inheritance of Summer' by Ada Clarke is a quiet masterpiece" (14 Apr
2026). Checks: opened that review; the answer gives the title (The
Inheritance of Summer) and the author (Ada Clarke).

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

CONTEXT_PAGES = ["/news/culture", "/news/books", "/latest"]
CONTEXT_SEARCHES = ["book review"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, ["book-review-the-inheritance-of-summer"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_states_book_title",
            mentions_title(ans, "The Inheritance of Summer"),
            "the reviewed book is 'The Inheritance of Summer'")
    j.check("answer_states_author", mentions_group(ans, ["ada clarke"]),
            "the author is Ada Clarke")

if __name__ == "__main__":
    run("BBC News--37", body)
