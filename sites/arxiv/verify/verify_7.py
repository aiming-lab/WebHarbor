#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--7.

Task: "Find the most recent paper submitted on machine learning in the Computer
Science category posted on ArXiv."

The site pins "today" at 2026-04-28. The cs papers matching both tokens
("machine", "learning") posted on 2026-04-28 — the newest announce day — are
hardcoded below (the date-sorted "machine learning" in cs search and the
cs.LG/cs new listings all put these first; the top entry is arXiv:2604.34272).

Checks (deterministic):
  nav:    a machine-learning cs search URL, a cs.LG/cs listing, or the /abs page
  answer: names one of the newest (2026-04-28) machine-learning cs papers
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, paper_mentioned,
                        navigated_to, Judge, parse_args)

CANDIDATES = [
    ("2604.34272", "Scaling laws for foundation models of machine learning"),
    ("2604.08527", "Demystifying OPD: Length Inflation and Stabilization Strategies for Large Language Models"),
    ("2604.07655", "Guardian-as-an-Advisor: Advancing Next-Generation Guardian Models for Trustworthy LLMs"),
    ("2604.07455", "Munkres' General Topology Autoformalized in Isabelle/HOL"),
    ("2604.07383", "SCOT: Multi-Source Cross-City Transfer with Optimal-Transport Soft-Correspondence Objective"),
    ("2604.07355", "Prediction Arena: Benchmarking AI Models on Real-World Prediction Markets"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--7", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((aid for aid, title in CANDIDATES
                    if paper_mentioned(fa, aid, title)), None)
    j.check("answer_names_newest_ml_cs_paper", matched is not None,
            f"matched={matched} final={fa[:220]!r}")
    if matched is None:
        j.emit()
    nav_ok = (any("/search" in u and "machine" in u and "learning" in u for u in urls)
              or any("/list/cs.lg" in u or "/list/cs/new" in u for u in urls)
              or navigated_to(t, f"/abs/{matched}"))
    j.check("nav_ml_cs_search_or_listing", nav_ok,
            f"urls={[u for u in urls if '/search' in u or '/list/cs' in u][:4]}")
    j.emit()


if __name__ == "__main__":
    main()
