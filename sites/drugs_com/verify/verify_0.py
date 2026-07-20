#!/usr/bin/env python3
"""Verifier for Drugs.com--0 (read-only). ibuprofen drug class + brand names.
Ground truth: class 'Nonsteroidal anti-inflammatory drugs'; brands Advil, Motrin, Nuprin.
Checks: nav /ibuprofen detail | answer names class + >=2 brands | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, drug_class_name,
                        drug_brands, contains_any, count_present, llm_text_match, Judge, parse_args)

SLUG = "ibuprofen"

def main():
    a = parse_args()
    j = Judge('Drugs.com--0', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    cls = drug_class_name(ref, SLUG); brands = drug_brands(ref, SLUG) or []
    j.check("nav_drug", navigated_to(t, f"/{SLUG}"), "opened the ibuprofen page")
    j.check("db_ground_truth", cls is not None and len(brands) >= 2, f"class={cls!r} brands={brands}")
    j.check("answer_class", contains_any(fa, ["nonsteroidal anti-inflammatory", "nsaid"]), f"final={fa!r}")
    j.check("answer_brands", brands and count_present(fa, brands) >= 2, f"brands={brands} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Drug class: {cls}. Brand names: {', '.join(brands)}.",
        "What is ibuprofen's drug class and what brand names are listed?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
