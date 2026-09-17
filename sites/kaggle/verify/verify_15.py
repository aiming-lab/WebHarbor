#!/usr/bin/env python3
"""Verifier for Kaggle--15 (read-only chain).

Open the 'Credit Card Fraud Transactions' dataset, find a public notebook that uses it, open
that notebook, and report its best leaderboard score. Ground truth: the only linked notebook is
'LightGBM Baseline for Real-Time Fraud Detection' (slug lgbm-baseline-fraud), best_score 0.91205.

Checks: nav dataset + the linked notebook | answer states the best score | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms, affirms_score, final_answer, llm_text_match,
                        load_run, navigated_to, origin_ok, parse_args, resolve_db,
                        run_complete, scalar, shot_at, shot_distinct, shot_final,
                        tables_unchanged)

DATASET = "credit-card-fraud-transactions"
NOTEBOOK = "lgbm-baseline-fraud"

def _score_ok(final, best):
    """Accept the literal stored score or a rounded form of it (e.g. 0.912)."""
    if best is None:
        return False
    if affirms(final, str(best)):
        return True
    try:
        return affirms_score(final, float(best))
    except (TypeError, ValueError):
        return False

def main():
    a = parse_args()
    j = Judge('Kaggle--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    best = scalar(ref, "notebooks", "best_score", NOTEBOOK)  # "0.91205"
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_dataset", navigated_to(t, f"/datasets/{DATASET}"), "opened the Credit Card Fraud dataset")
    j.check("nav_notebook", navigated_to(t, f"/code/{NOTEBOOK}"), "opened the linked notebook")
    j.check("db_ground_truth", best is not None, f"best_score={best!r}")
    j.check("answer_best_score", _score_ok(fa, best), f"expected={best!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The notebook's best leaderboard score is {best}.",
        "What is the best leaderboard score of the public notebook that uses the Credit Card Fraud dataset?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/code/lgbm-baseline-fraud")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
