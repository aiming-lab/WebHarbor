#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--21.

Task: "Search for papers on 'neural networks for image processing' in the
Computer Science category on ArXiv and report how many were submitted in the
last week."

The site's search for "neural networks for image processing" with category=cs
and the last-week window (last_days=7) returns exactly 14 results.

Checks (deterministic):
  nav:    a /search URL with the query tokens and a week window or the cs
          category (manual cs filtering from the result cards is also valid)
  answer: 14 bound to result/paper words, or >=3 of the five core titles named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

CORE_PAPERS = [
    ("2604.63105", "Self-supervised learning for neural networks in image processing"),
    ("2604.60001", "Convolutional neural networks for low-light image denoising"),
    ("2604.60002", "Transformer-based neural networks for medical image processing"),
    ("2604.60003", "Lightweight neural networks for on-device image processing"),
    ("2604.60004", "Self-supervised neural networks for image processing under domain shift"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--21", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any(
        "/search" in u and "neural" in u and "image" in u
        and ("last_days" in u or "date_from" in u or "category=cs" in u
             or "primary_category=cs" in u)
        for u in urls)
    j.check("nav_cs_image_processing_week_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 14, "result", "results", "paper", "papers",
                     "article", "articles", "submission", "submissions")
    named = sum(1 for aid, title in CORE_PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_14_weekly_results", count_ok or named >= 3,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
