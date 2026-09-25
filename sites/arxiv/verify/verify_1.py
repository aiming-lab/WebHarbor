#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--1.

Task: "Search for the latest research papers on quantum computing submitted to
ArXiv within the last two days."

The site pins "today" at 2026-04-28; "within the last two days" is the site's
last_days=2 window (2026-04-27..28), which its own search returns exactly 10
papers for (hardcoded below). Browsing the quant-ph new listing's day groups
and reporting the last-two-days papers is the equivalent natural path, so the
navigation check accepts either route.

Checks (deterministic):
  nav:    a /search URL with both query tokens AND a two-day window parameter,
          OR the quant-ph new listing
  answer: names at least 2 distinct papers from the 10-paper result set
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, paper_mentioned,
                        Judge, parse_args)

RESULT_PAPERS = [
    ("2604.43728", "Detection of continuous gravitational waves from a spinning neutron star"),
    ("2604.40002", "Variational quantum eigensolvers for strongly correlated electrons"),
    ("2604.40001", "Error-corrected quantum computing with neutral atom arrays"),
    ("2604.04083", "Parent Selection Mechanisms in Elitist Crossover-Based Algorithms"),
    ("2604.40626", "Binary black hole merger catalog from LIGO O5"),
    ("2604.40003", "Benchmarking noise-adaptive compilation on superconducting processors"),
    ("2604.13382", "Causal machine learning with instrumental variables"),
    ("2604.08182", "Wattlytics: A Web Platform for Co-Optimizing Performance, Energy, and TCO in HPC Clusters"),
    ("2604.07954", "Quantum Property Testing for Bounded-Degree Directed Graphs"),
    ("2604.07782", "Ghost imaging with zero photons"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--1", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_window = any(
        ("/search" in u and "quantum" in u and "computing" in u
         and ("last_days=2" in u or "date_from" in u or "date_to" in u))
        or "/list/quant-ph" in u
        for u in urls)
    j.check("nav_quantum_computing_2day_search", nav_window,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    matched = {aid for aid, title in RESULT_PAPERS if paper_mentioned(fa, aid, title)}
    j.check("answer_lists_2day_results", len(matched) >= 2,
            f"matched={sorted(matched)} final={fa[:220]!r}")
    j.emit()


if __name__ == "__main__":
    main()
