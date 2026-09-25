#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--4.

Task: "Find the most recent research papers in Astrophysics of Galaxies. How
many papers have been announced in the last day?"

The site pins "today" at 2026-04-28. The astro-ph.GA listing's most recent
announce day is 2026-04-28 with exactly 1 paper ("The stellar mass function of
galaxies at z > 6", arXiv:2604.69678); the site's own last_days=1 search gives
the same 1 paper.

Checks (deterministic):
  nav:    an astro-ph.GA page (listing/category) or a galaxies search
  answer: 1 announced paper (count bound to paper-words, or the paper named)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

LAST_DAY_PAPER = ("2604.69678", "The stellar mass function of galaxies at z > 6")


def main():
    a = parse_args()
    j = Judge("ArXiv--4", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ga = any(
        "astro-ph.ga" in u or "/category/astro-ph" in u
        or ("/search" in u and "galax" in u) for u in urls)
    j.check("nav_astro_ph_ga", nav_ga,
            f"urls={[u for u in urls if 'astro' in u or 'galax' in u][:4]}")
    count_ok = counts(fa, 1, "paper", "papers", "entry", "entries",
                      "article", "articles", "submission", "submissions")
    named = paper_mentioned(fa, *LAST_DAY_PAPER)
    j.check("answer_one_paper_last_day", count_ok or named,
            f"count_bound={count_ok} named={named} final={fa[:220]!r}")
    j.emit()


if __name__ == "__main__":
    main()
