#!/usr/bin/env python3
"""Verifier for Kaggle--1 (read-only).

Open 'Home Credit Default Risk 2026' (slug credit-default-risk-2026) and report the scoring
metric. Ground truth: metric == "ROC AUC".

Checks: nav competition detail | answer names the metric | LLM anchor.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, scalar,
                        contains_any, llm_text_match, Judge, parse_args)

SLUG = "credit-default-risk-2026"

def main():
    a = parse_args()
    j = Judge('Kaggle--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    gt = scalar(ref, "competitions", "metric", SLUG)  # "ROC AUC"
    j.check("nav_competition", navigated_to(t, f"/competitions/{SLUG}"), "opened the Home Credit competition page")
    j.check("db_ground_truth", gt is not None, f"metric={gt!r}")
    j.check("answer_metric", contains_any(fa, ["roc auc", "auc"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The scoring metric is {gt}.",
        "Which evaluation metric scores submissions in the Home Credit Default Risk 2026 competition?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
