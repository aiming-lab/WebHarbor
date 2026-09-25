#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--9.

Task: "Find the latest research paper about neural networks published on ArXiv
which has been submitted within the last week."

The site pins "today" at 2026-04-28. The only paper matching both query tokens
("neural", "networks") inside the last-7-days window on 2026-04-28 — and the
top entry of the date-sorted "neural networks" search — is arXiv:2604.60001
"Convolutional neural networks for low-light image denoising" (2026-04-28).

Checks (deterministic):
  nav:    a neural-networks search URL or the paper's /abs page
  answer: names arXiv:2604.60001 (title prefix or id)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, paper_mentioned,
                        navigated_to, Judge, parse_args)

PAPER = ("2604.60001", "Convolutional neural networks for low-light image denoising")


def main():
    a = parse_args()
    j = Judge("ArXiv--9", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = (any("/search" in u and "neural" in u and "network" in u for u in urls)
              or navigated_to(t, "/abs/2604.60001"))
    j.check("nav_neural_networks_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    j.check("answer_names_latest_weekly_nn_paper",
            paper_mentioned(fa, *PAPER), f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
