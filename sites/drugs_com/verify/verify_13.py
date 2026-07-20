#!/usr/bin/env python3
"""Verifier for Drugs.com--13 (read-only). White oval pills: first 3 drug + imprint.
Ground truth: multiple white oval pills exist (ibuprofen I-2, ibuprofen IP 466, metformin Z 70,
lisinopril 10 MG, atorvastatin PD 156, ...). We verify the answer lists >=3 white-oval pills
that actually exist in the catalog (by generic name + imprint pairing).
Checks: nav pill identifier | answer lists >=3 valid white-oval pills w/ imprints | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, db_query, norm,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--13', a.no_llm)
    t = load_run(a.run_dir); fa = norm(final_answer(t))
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT d.generic_name, di.imprint FROM drug_image di JOIN drug d ON d.id=di.drug_id "
                         "WHERE lower(di.color)='white' AND lower(di.shape)='oval'")
    pills = [(r[0], r[1]) for r in rows] if rows else []
    # count how many white-oval pills the answer names WITH their imprint (both tokens present)
    matched = [(g, imp) for g, imp in pills if norm(g) in fa and norm(imp) in fa]
    distinct_drugs = {g for g, _ in matched}
    j.check("nav_pill_identifier", navigated_any(t, ["/pill-identifier", "/drug-identifier", "/pill_identification"]),
            "used the pill identifier")
    j.check("db_ground_truth", len(pills) >= 3, f"white_oval_count={len(pills)}")
    j.check("answer_lists_3_pills", len(matched) >= 3 and len(distinct_drugs) >= 3,
            f"matched={matched} distinct_drugs={sorted(distinct_drugs)}")
    ok, ev = llm_text_match(final_answer(t), f"Any 3 of these white oval pills (drug, imprint): {pills}",
        "List 3 white oval pills with their drug names and imprint codes.")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
