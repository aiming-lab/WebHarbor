#!/usr/bin/env python3
"""Verifier for Drugs.com--2 (read-only). ibuprofen + warfarin interaction.
Ground truth: severity 'major'; risk = increased serious bleeding (GI/hemorrhage).
Checks: nav interaction checker | answer states major + bleeding risk | LLM anchor."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, db_query,
                        contains_any, contains_all, llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--2', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref,
        "SELECT i.severity FROM drug_interaction i JOIN drug da ON da.id=i.drug_a_id "
        "JOIN drug db ON db.id=i.drug_b_id WHERE (da.slug='ibuprofen' AND db.slug='warfarin') "
        "OR (da.slug='warfarin' AND db.slug='ibuprofen')")
    sev = rows[0][0] if rows else None  # 'major'
    j.check("nav_interaction_checker",
            navigated_any(t, ["/interaction-checker", "/drug-interactions", "/drug_interactions", "/api/interaction-check"]),
            "used the interaction checker")
    j.check("db_ground_truth", sev is not None, f"severity={sev!r}")
    j.check("answer_severity", sev is not None and contains_any(fa, [sev]), f"expected={sev!r} final={fa!r}")
    j.check("answer_risk", contains_any(fa, ["bleed", "bleeding", "hemorrhage", "gi"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, f"Severity: {sev}. Main risk: significantly increased risk of serious bleeding.",
        "What is the severity and main risk of the ibuprofen + warfarin interaction?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
