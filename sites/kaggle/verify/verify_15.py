#!/usr/bin/env python3
"""Verifier for Kaggle--15 (read-only chain).

Open the 'Credit Card Fraud Transactions' dataset, find a public notebook that uses it, open
that notebook, and report its best leaderboard score. Ground truth: the only linked notebook is
'LightGBM Baseline for Real-Time Fraud Detection' (slug lgbm-baseline-fraud), best_score 0.91205.

Checks: nav dataset + the linked notebook | answer states the best score | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, scalar, db_query,
                        contains_any, contains_score, llm_text_match, Judge, parse_args)

DATASET = "credit-card-fraud-transactions"
NOTEBOOK = "lgbm-baseline-fraud"

def _score_ok(final, best):
    """Accept the literal stored score or a rounded form of it (e.g. 0.912)."""
    if best is None:
        return False
    if contains_any(final, [str(best)]):
        return True
    try:
        return contains_score(final, float(best))
    except (TypeError, ValueError):
        return False

def main():
    a = parse_args()
    j = Judge('Kaggle--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    best = scalar(ref, "notebooks", "best_score", NOTEBOOK)  # "0.91205"
    j.check("nav_dataset", navigated_to(t, f"/datasets/{DATASET}"), "opened the Credit Card Fraud dataset")
    j.check("nav_notebook", navigated_to(t, f"/code/{NOTEBOOK}"), "opened the linked notebook")
    j.check("db_ground_truth", best is not None, f"best_score={best!r}")
    j.check("answer_best_score", _score_ok(fa, best), f"expected={best!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The notebook's best leaderboard score is {best}.",
        "What is the best leaderboard score of the public notebook that uses the Credit Card Fraud dataset?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
