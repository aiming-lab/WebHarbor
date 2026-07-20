#!/usr/bin/env python3
"""Verifier for Drugs.com--16 (read-only). Benzodiazepines class: >=3 drugs.
Ground truth: alprazolam, clonazepam, lorazepam, diazepam, temazepam (class slug 'benzodiazepines').
Checks: nav drug-class/benzodiazepines | answer lists >=3 | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, drugs_in_class,
                        count_present, norm, llm_text_match, Judge, parse_args)

CLASS = "benzodiazepines"

def main():
    a = parse_args()
    j = Judge('Drugs.com--16', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    drugs = drugs_in_class(ref, CLASS)
    # Require the specific class page (slug), not the bare /drug-classes index (which lists
    # class names only, not member drugs). Member drugs are LLM-guessable.
    j.check("nav_class", navigated_any(t, [f"/drug-class/{CLASS}", f"/drug-classes/{CLASS}"]),
            "opened the Benzodiazepines class page")
    j.check("db_ground_truth", drugs is not None and len(drugs) >= 3, f"drugs={drugs}")
    j.check("answer_lists_3", drugs is not None and count_present(fa, drugs) >= 3,
            f"matched={None if drugs is None else [d for d in drugs if norm(d) in norm(fa)]}")
    ok, ev = llm_text_match(fa, f"At least 3 of these benzodiazepines: {drugs}",
        "List at least 3 drugs in the Benzodiazepines class.")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
