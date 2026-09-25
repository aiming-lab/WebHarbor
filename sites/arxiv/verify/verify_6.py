#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--6.

Task: "How many figures and tables are in the paper \"On the Sentence Embeddings
from Pre-trained Language Models\"?"

The paper's abstract page (/abs/2011.05864) shows Comments: "EMNLP 2020,
5 figures, 7 tables".

Checks (deterministic):
  nav:    the paper's /abs (or /pdf) page, or a title search that surfaces it
  answer: 5 bound to figures AND 7 bound to tables
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, counts,
                        navigated_to, Judge, parse_args)

FIGURES = 5
TABLES = 7


def main():
    a = parse_args()
    j = Judge("ArXiv--6", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    nav_paper = (navigated_to(t, "/abs/2011.05864")
                 or navigated_to(t, "/pdf/2011.05864")
                 or any("/search" in u and "sentence" in u.lower()
                        and "embeddings" in u.lower() for u in step_urls(t)))
    j.check("nav_sentence_embeddings_paper", nav_paper,
            f"urls={[u for u in step_urls(t) if '2011.05864' in u or '/search' in u][:4]}")
    j.check("answer_5_figures", counts(fa, FIGURES, "figure", "figures"),
            f"final={fa[:220]!r}")
    j.check("answer_7_tables", counts(fa, TABLES, "table", "tables"),
            f"final={fa[:220]!r}")
    j.emit()


if __name__ == "__main__":
    main()
