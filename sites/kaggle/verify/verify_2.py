#!/usr/bin/env python3
"""Verifier for Kaggle--2 (read-only).

Among datasets tagged 'climate', which has the most upvotes? Ground truth: 'Global Temperature
Anomalies 1880–2025' (2240 upvotes; next is CO2 Emissions at 1842).

Checks: nav the datasets listing | answer names the top dataset | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, db_query,
                        contains_any, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Kaggle--2', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT title, upvotes FROM datasets WHERE tags_json LIKE '%climate%' ORDER BY upvotes DESC")
    top = rows[0][0] if rows else None  # "Global Temperature Anomalies 1880–2025"
    j.check("nav_datasets", navigated_to(t, "/datasets"), "opened the datasets area")
    j.check("db_ground_truth", top is not None and (len(rows) < 2 or rows[0][1] > rows[1][1]),
            f"top={top!r} rows={[(r[0], r[1]) for r in (rows or [])][:3]}")
    j.check("answer_top_dataset", contains_any(fa, ["global temperature anomalies", "temperature anomalies"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"The most-upvoted climate-tagged dataset is '{top}'.",
        "Among datasets tagged 'climate', which one has the most upvotes?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
