#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--31.

Task: "Search ArXiv for papers with 'Graph Neural Networks' in the abstract that
were submitted between Jan 1, 2024, and Jan 3, 2024, and determine how many of
these papers have more than five authors."

An abstract search for "Graph Neural Networks" over 2024-01-01..2024-01-03
returns 6 papers; exactly 3 of them have more than five authors
(arXiv:2401.38094, 2401.61847, 2401.50875 — each with 6 authors; the result
cards show "(N authors)").

Checks (deterministic):
  nav:    a graph-neural-networks abstract search with the 2024-01-01..03 window
  answer: 3 bound to paper/article words (or 3 + "more than five")
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts, has_number,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--31", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any(
        "/search" in u and "graph" in u and "neural" in u
        and ("searchtype=abstract" in u or "date_from" in u)
        for u in urls)
    j.check("nav_gnn_abstract_date_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    f = fa.lower()
    count_ok = counts(fa, 3, "paper", "papers", "article", "articles") or (
        has_number(fa, 3) and "more than five" in f)
    j.check("answer_3_papers_over_five_authors", count_ok,
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
