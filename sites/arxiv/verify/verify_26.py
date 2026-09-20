#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--26.

Task: "Search for papers related to 'climate change modeling' on ArXiv and find
out how many have been published in the Earth and Planetary Astrophysics
(astro-ph.EP) category in the last week."

The site pins "today" at 2026-04-28. Searching "climate change modeling" with
category=astro-ph.EP and the last-week window returns exactly 5 papers
(hardcoded below).

Checks (deterministic):
  nav:    an on-site climate-change-modeling search with a week window or the
          astro-ph.EP category (an agent may instead restrict by reading the
          result cards' subject labels)
  answer: 5 bound to paper/article words, or >=3 of the 5 titles named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

PAPERS = [
    ("2604.11007", "Climate change modeling of exoplanet atmospheres"),
    ("2604.27394", "Planetary climate change modeling under high stellar flux"),
    ("2604.28603", "Orbital dynamics and long-term climate change modeling on Mars"),
    ("2604.94379", "Early Earth habitability from climate change modeling"),
    ("2604.09004", "Climate Change Modeling on Terrestrial Exoplanets Using 3D Circulation Models"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--26", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/search" in u and "climate" in u
                 and ("astro-ph.ep" in u or "last_days" in u or "date_from" in u)
                 for u in urls)
    j.check("nav_climate_astroph_ep_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 5, "paper", "papers", "article", "articles",
                      "result", "results")
    named = sum(1 for aid, title in PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_5_ep_papers", count_ok or named >= 3,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
