#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--18.

Task: "Download the paper 'Dense Passage Retrieval for Open-Domain Question
Answering'. How many formulas are in the article and which one is the loss
function?"

The paper's abstract page (/abs/2004.04906) shows Comments: "EMNLP 2020,
9 formulas, 6 tables, 3 figures" and the locally served PDF is the real DPR
paper, whose loss is the in-batch negative log-likelihood over the similarity
sim(q, p) (the seeded loss-function field for this paper is
"L = -log[ exp(sim(q, p+)) / (exp(sim(q, p+)) + sum_i exp(sim(q, p-_i))) ]").

Checks (deterministic):
  nav:    the paper's /abs or /pdf page
  answer: 9 bound to formulas AND a similarity-based (sim(q, ...)) negative
          log-likelihood loss function
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, counts, navigated_to,
                        navigated_any, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--18", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    nav_ok = navigated_any(t, ["/abs/2004.04906", "/pdf/2004.04906"])
    j.check("nav_dpr_paper", nav_ok,
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '2004.04906' in u][:4]}")
    j.check("answer_9_formulas", counts(fa, 9, "formula", "formulas"),
            f"final={fa[:240]!r}")
    f = fa.lower()
    sim_loss = bool(re.search(r"sim\s*\(\s*q", f)) or (
        "similarity" in f and "negative log" in f)
    j.check("answer_loss_function_sim_qp", sim_loss, f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
