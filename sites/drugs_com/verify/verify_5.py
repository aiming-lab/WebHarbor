#!/usr/bin/env python3
"""Verifier for Drugs.com--5 (read-only). sertraline brands + conditions.
Ground truth: brand Zoloft; conditions include depression, anxiety, OCD, PTSD, panic disorder.
Checks: nav /sertraline | answer names Zoloft + >=2 conditions | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, drug_brands, drug_field,
                        contains_any, count_present, llm_text_match, Judge, parse_args)
import json as _json

SLUG = "sertraline"

def main():
    a = parse_args()
    j = Judge('Drugs.com--5', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    brands = drug_brands(ref, SLUG) or []
    try:
        conds = _json.loads(drug_field(ref, SLUG, "conditions_json") or "[]")
    except Exception:
        conds = []
    cond_words = [c.replace("_", " ") for c in conds]
    j.check("nav_drug", navigated_to(t, f"/{SLUG}"), "opened the sertraline page")
    j.check("db_ground_truth", brands and conds, f"brands={brands} conds={conds}")
    j.check("answer_brand", contains_any(fa, brands or ["zoloft"]), f"brands={brands} final={fa!r}")
    j.check("answer_conditions",
            count_present(fa, cond_words + ["depression", "anxiety", "ocd", "ptsd", "panic"]) >= 2,
            f"conds={cond_words} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Brand names: {', '.join(brands)}. Treats: {', '.join(cond_words)}.",
        "What are sertraline's brand names and what conditions does it treat?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
