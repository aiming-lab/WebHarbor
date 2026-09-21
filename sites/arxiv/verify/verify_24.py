#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--24.

Task: "Identify the most recent paper related to 'graph neural networks' on ArXiv
and determine the affiliation of the first author."

The newest genuine graph-neural-networks papers on the mirror are hardcoded
below (top of the date-sorted search / GNN title matches).

NOTE (quality audit): the affiliation half of this task is NOT verifiable —
the mirror renders author names only; the affiliation column exists in the DB
but no template displays it. The grading contract below anchors the
identifiable half: which paper is the most recent GNN paper.

Checks (deterministic):
  nav:    a graph-neural-networks search URL or a candidate /abs page
  answer: names one of the most recent GNN papers
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, paper_mentioned,
                        navigated_to, Judge, parse_args)

CANDIDATES = [
    ("2604.79721", "Graph neural networks for protein interaction prediction"),
    ("2604.67035", "Graph neural networks with attention over hypergraphs"),
    ("2604.07781", "Toward Generalizable Graph Learning for 3D Engineering AI"),
    ("2604.40020", "Learning quantum circuit ansatzes with graph neural networks"),
    ("2604.08131", "Graph Neural Networks for Misinformation Detection"),
    ("2604.07891", "AFGNN: API Misuse Detection using Graph Neural Networks and Clustering"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--24", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    matched = next((aid for aid, title in CANDIDATES
                    if paper_mentioned(fa, aid, title)), None)
    j.check("answer_names_recent_gnn_paper", matched is not None,
            f"matched={matched} final={fa[:240]!r}")
    if matched is None:
        j.emit()
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = (any("/search" in u and "graph" in u and "neural" in u for u in urls)
              or navigated_to(t, f"/abs/{matched}"))
    j.check("nav_gnn_search_or_paper", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    j.emit()


if __name__ == "__main__":
    main()
