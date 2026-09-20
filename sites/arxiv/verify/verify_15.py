#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--15.

Task: "Searching Chinese Benchmark on ArXiv, how many papers announced in
December 2023 mention being accepted for AAAI 2024?"

A search for "Chinese Benchmark" restricted to December 2023 returns 9 papers;
exactly 6 of them mention AAAI 2024 (journal-ref / comments on the result
cards). The 6 are hardcoded below.

Checks (deterministic):
  nav:    a Chinese-Benchmark search with a December-2023 window
  answer: 6 bound to paper/article words, or >=5 of the 6 AAAI titles named
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        paper_mentioned, Judge, parse_args)

AAAI_PAPERS = [
    ("2312.01234", "A Comprehensive Chinese Benchmark for Natural Language Understanding"),
    ("2312.05678", "Chinese Benchmark for Multimodal Reasoning in Large Language Models"),
    ("2312.09876", "Multi-domain Chinese Benchmark for Code and Text Understanding"),
    ("2312.43699", "A Comprehensive Chinese Benchmark for Evaluating Large Language Models"),
    ("2312.62553", "C-Eval: A Multi-Level Chinese Benchmark for Foundation Models"),
    ("2312.58934", "Chinese Benchmark for Legal Document Understanding"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--15", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any(
        "/search" in u and "chinese" in u and "benchmark" in u
        and ("2023-12" in u or "month=12" in u or "year=2023" in u
             or "date_from" in u)
        for u in urls)
    j.check("nav_chinese_benchmark_dec2023_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    count_ok = counts(fa, 6, "paper", "papers", "article", "articles")
    named = sum(1 for aid, title in AAAI_PAPERS if paper_mentioned(fa, aid, title))
    j.check("answer_6_aaai2024_papers", count_ok or named >= 5,
            f"count_bound={count_ok} named={named} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
