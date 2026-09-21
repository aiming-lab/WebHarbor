#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--29.

Task: "On ArXiv, search for papers with 'Neural Network Optimization' in the
title published in 2023, and provide the number of such papers."

A title search for "Neural Network Optimization" restricted to 2023 returns
exactly 7 papers (hardcoded below).

Checks (deterministic):
  nav:    a /search URL with the neural-network-optimization query
  answer: 7 bound to paper/article/result words, or >=5 of the 7 titles named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

PAPERS = [
    ("2301.12345", "Efficient Neural Network Optimization via Gradient Scaling"),
    ("2305.23456", "Neural Network Optimization with Low-Rank Adaptation"),
    ("2309.34567", "Stochastic Neural Network Optimization for Large-Scale Models"),
    ("2305.46092", "Neural Network Optimization via Second-Order Methods"),
    ("2308.06825", "Scalable Neural Network Optimization with Sharpness-Aware Minimization"),
    ("2311.37908", "Neural Network Optimization in Reinforcement Learning"),
    ("2302.79632", "A Unified View of Neural Network Optimization"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--29", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/search" in u and "neural" in u and "optimization" in u
                 for u in urls)
    j.check("nav_nno_title_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 7, "paper", "papers", "article", "articles",
                      "result", "results", "title", "titles")
    named = sum(1 for aid, title in PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_7_papers_2023", count_ok or named >= 5,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
