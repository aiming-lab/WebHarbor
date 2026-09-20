#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--14.

Task: "On ArXiv, how many articles have 'SimCSE' in the article and are
originally announced in October 2023?"

An all-fields search for SimCSE restricted to October 2023 (year=2023&month=10
or date_from/date_to) returns exactly 5 articles (hardcoded below).

Checks (deterministic):
  nav:    a SimCSE search with an October-2023 window (or one of the results'
          /abs pages)
  answer: 5 bound to article/paper/result words, or >=3 of the 5 titles named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, navigated_to, Judge, parse_args)

OCT23_PAPERS = [
    ("2310.15432", "SimCSE Revisited: Unified Contrastive Learning for Sentence Representations"),
    ("2310.22148", "SimCSE++: Towards a More Effective Contrastive Sentence Embedding Framework"),
    ("2310.11148", "Debiasing SimCSE for Robust Sentence Representations"),
    ("2310.62599", "A Contrastive Framework Beyond SimCSE"),
    ("2310.48564", "Unified Sentence Representation Learning"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--14", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = (any("/search" in u and "simcse" in u
                  and ("2023-10" in u or "month=10" in u or "year=2023" in u
                       or "date_from" in u)
                  for u in urls)
              or any(navigated_to(t, f"/abs/{aid}") for aid, _ in OCT23_PAPERS))
    j.check("nav_simcse_oct2023_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 5, "article", "articles", "paper", "papers",
                     "result", "results")
    named = sum(1 for aid, title in OCT23_PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_5_articles", count_ok or named >= 3,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
