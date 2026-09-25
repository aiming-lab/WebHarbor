#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--23.

Task: "Determine how many articles with the keyword 'autonomous vehicles' were
published in the 'Electrical Engineering and Systems Science' section of ArXiv
yesterday."

The site pins "today" at 2026-04-28 (banner on every page: "'yesterday' wording
is relative to this date"), so yesterday is 2026-04-27. Searching "autonomous
vehicles" in eess on 2026-04-27 returns 2 papers (arXiv:2604.81965,
arXiv:2604.70001); the last_days=1 reading (2026-04-28) also yields 2 papers
(arXiv:2604.39694, arXiv:2604.54152) — the count is 2 either way.

Checks (deterministic):
  nav:    an autonomous-vehicles search URL (eess or date-windowed)
  answer: 2 bound to article/paper words, or >=2 of the four papers named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

PAPERS = [
    ("2604.81965", "Sensor fusion for autonomous vehicles with LiDAR and vision"),
    ("2604.70001", "Model predictive trajectory planning for autonomous vehicles at unsignalised intersections"),
    ("2604.39694", "Autonomous vehicles perception in adverse weather conditions"),
    ("2604.54152", "End-to-end control for autonomous vehicles via reinforcement learning"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--23", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/search" in u and "autonomous" in u and "vehicle" in u for u in urls)
    j.check("nav_autonomous_vehicles_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 2, "article", "articles", "paper", "papers",
                     "result", "results")
    named = sum(1 for aid, title in PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_2_articles_yesterday", count_ok or named >= 2,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
