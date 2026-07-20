#!/usr/bin/env python3
"""Verifier for Drugs.com--17 (read-only). Fluoroquinolone: generic + brand + conditions.
Ground truth: ciprofloxacin (Cipro), levofloxacin (Levaquin), moxifloxacin (Avelox); treat
bacterial infections / UTI / pneumonia.
Checks: nav search/class | answer names a fluoroquinolone generic + its brand + a condition | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, db_query,
                        contains_any, norm, llm_text_match, Judge, parse_args)
import json as _json

def main():
    a = parse_args()
    j = Judge('Drugs.com--17', a.no_llm)
    t = load_run(a.run_dir); fa = norm(final_answer(t))
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    rows = db_query(ref, "SELECT d.generic_name, d.brand_names_json, d.conditions_json FROM drug d "
                         "JOIN drug_class dc ON dc.id=d.drug_class_id WHERE dc.name LIKE '%luoroquinolone%'")
    # find a fluoroquinolone the answer actually reports: generic + >=1 brand + >=1 condition
    hit = None
    for generic, brands_json, conds_json in (rows or []):
        try:
            brands = _json.loads(brands_json or "[]")
        except Exception:
            brands = []
        try:
            conds = [c.replace("_", " ") for c in _json.loads(conds_json or "[]")]
        except Exception:
            conds = []
        if norm(generic) in fa and any(norm(b) in fa for b in brands) \
           and (any(norm(c) in fa for c in conds) or any(w in fa for w in ["infection", "uti", "pneumonia", "bacterial"])):
            hit = (generic, brands, conds); break
    # Require a specific fluoroquinolone detail page (or its class page). Generic/brand/condition
    # are all LLM-recallable, so a bare /search must not satisfy the anti-shortcut gate.
    j.check("nav_fluoroquinolone",
            navigated_any(t, ["/ciprofloxacin", "/levofloxacin", "/moxifloxacin",
                              "/drug-class/fluoroquinolones", "/drug-classes/fluoroquinolones"]),
            "opened a fluoroquinolone detail/class page")
    j.check("db_ground_truth", rows is not None and len(rows) >= 1, f"fluoroquinolones={[r[0] for r in (rows or [])]}")
    j.check("answer_generic_brand_condition", hit is not None, f"hit={hit}")
    ok, ev = llm_text_match(final_answer(t),
        f"A fluoroquinolone with its brand and conditions, e.g. {[(r[0]) for r in (rows or [])]}, treating bacterial infections/UTI/pneumonia.",
        "Report a fluoroquinolone's generic name, brand name(s), and what conditions it treats.")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
