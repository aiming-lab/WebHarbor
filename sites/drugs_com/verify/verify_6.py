#!/usr/bin/env python3
"""Verifier for Drugs.com--6 (read-only). Conditions page 'diabetes': >=4 drugs.
Ground truth: metformin, semaglutide, sitagliptin, empagliflozin, glipizide, ... (DB set).
Checks: nav /condition/diabetes | answer lists >=4 valid diabetes drugs | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, drugs_for_condition,
                        norm, count_present, llm_text_match, Judge, parse_args)

COND = "diabetes"

def main():
    a = parse_args()
    j = Judge('Drugs.com--6', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    drugs = drugs_for_condition(ref, COND)
    j.check("nav_condition", navigated_any(t, [f"/condition/{COND}", f"/conditions/{COND}"]),
            "opened the diabetes conditions page")
    j.check("db_ground_truth", drugs is not None and len(drugs) >= 4, f"count={None if drugs is None else len(drugs)}")
    j.check("answer_lists_4", drugs is not None and count_present(fa, drugs) >= 4,
            f"matched={None if drugs is None else [d for d in drugs if norm(d) in norm(fa)]}")
    ok, ev = llm_text_match(fa, f"At least 4 of these diabetes drugs: {drugs}",
        "Name at least 4 drugs listed for diabetes.")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
