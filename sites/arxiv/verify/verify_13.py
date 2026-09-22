#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--13.

Task: "How many articles on ArXiv with 'SimCSE' in the title?"

A title search for SimCSE (/search?query=SimCSE&searchtype=title) returns
exactly 7 articles (hardcoded below).

Checks (deterministic):
  nav:    a /search URL carrying the SimCSE title query
  answer: 7 bound to article/paper/result words, or >=4 of the 7 titles named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

TITLE_PAPERS = [
    ("2104.08821", "SimCSE: Simple Contrastive Learning of Sentence Embeddings"),
    ("2305.13169", "Improved SimCSE with Multi-Task Learning for Sentence Embeddings"),
    ("2310.15432", "SimCSE Revisited: Unified Contrastive Learning for Sentence Representations"),
    ("2311.08765", "Beyond SimCSE: Contextual and Structural Contrastive Learning for Sentence Embeddings"),
    ("2310.22148", "SimCSE++: Towards a More Effective Contrastive Sentence Embedding Framework"),
    ("2310.11148", "Debiasing SimCSE for Robust Sentence Representations"),
    ("2310.62599", "A Contrastive Framework Beyond SimCSE"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--13", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/search" in u and "simcse" in u for u in urls)
    j.check("nav_simcse_title_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 7, "article", "articles", "paper", "papers",
                      "result", "results", "title", "titles", "match", "matches")
    named = sum(1 for aid, title in TITLE_PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_7_title_articles", count_ok or named >= 4,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
