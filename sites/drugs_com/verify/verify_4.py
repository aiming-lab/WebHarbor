#!/usr/bin/env python3
"""Verifier for Drugs.com--4 (read-only). Drugs A-Z: 5 generics starting with 'L'.
Ground truth: any 5 real drugs whose generic starts with L (lamotrigine, lansoprazole,
levofloxacin, levothyroxine, lisinopril, losartan, ...). We verify against the DB set.
Checks: nav Drugs A-Z | answer lists >=5 valid L-drugs from the catalog | LLM."""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, db_query, norm,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--4', a.no_llm)
    t = load_run(a.run_dir); fa = norm(final_answer(t))
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT generic_name FROM drug WHERE generic_name LIKE 'l%'")
    l_drugs = {r[0].lower() for r in rows} if rows else set()
    matched = sorted({d for d in l_drugs if d in fa})
    # Require the A-Z page AND the letter=L filter view — the 5 L-drugs are common enough to
    # recall, so opening the default A-Z landing page alone isn't proof of navigation.
    j.check("nav_drugs_az", navigated_any(t, ["/drugs-a-z", "/drug-az", "/drugs-a-to-z", "/drug_information"]),
            "opened the Drugs A-Z page")
    j.check("nav_letter_L", navigated_any(t, ["letter=L", "letter=l"]),
            f"filtered to letter L ({[u for u in [s.get('url','') for s in t.get('steps', [])] if 'letter=' in u]})")
    j.check("db_ground_truth", len(l_drugs) >= 5, f"catalog_L_count={len(l_drugs)}")
    j.check("answer_lists_5_L_drugs", len(matched) >= 5, f"matched={matched}")
    ok, ev = llm_text_match(final_answer(t),
        f"Any 5 drugs whose generic name starts with L, e.g. {sorted(l_drugs)[:8]}.",
        "List 5 drugs whose generic names start with the letter L.")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
