#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--20.

Task: "Find the latest paper on 'machine learning in the Statistics section of
ArXiv and provide its abstract."

The newest paper in the Statistics section's Machine Learning area is
arXiv:2604.50001 "Stability selection via cross-fitted machine learning"
(stat.ML, 2026-04-28) — top of both the stat.ML listing and the
machine-learning-in-stat search; arXiv:2604.45108 (stat.ML, 2026-04-28) is the
same-day alternative.

Checks (deterministic):
  nav:    a stat.ML listing / Statistics search / the paper's /abs page
  answer: names one of the two newest stat.ML papers AND gives its abstract
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, contains_all,
                        paper_mentioned, navigated_to, Judge, parse_args)

# (arxiv_id, title, abstract chunk, abstract keywords)
CANDIDATES = [
    ("2604.50001", "Stability selection via cross-fitted machine learning",
     "we develop a stability selection procedure that leverages cross-fitted machine learning predictions",
     ["stability selection", "cross-fitted", "p-values", "nuisance"]),
    ("2604.45108", "Bayesian deep learning for uncertainty quantification in regression",
     "we develop a bayesian neural network approach to quantify predictive uncertainty in",
     ["bayesian", "uncertainty", "regression", "variational"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--20", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_newest_statml_paper", matched is not None,
            f"final={fa[:240]!r}")
    if matched is None:
        j.emit()
    aid, title, chunk, keywords = matched
    nav_ok = (navigated_to(t, f"/abs/{aid}")
              or any("/list/stat.ml" in u or "category=stat" in u for u in urls))
    j.check("nav_statml", nav_ok,
            f"urls={[u for u in urls if 'stat' in u][:4]}")
    f = norm(fa)
    abstract_ok = (chunk in f) or contains_all(fa, keywords[:2])
    j.check("answer_gives_abstract", abstract_ok, f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
