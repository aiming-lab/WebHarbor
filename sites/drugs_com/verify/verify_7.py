#!/usr/bin/env python3
"""Verifier for Drugs.com--7 (read-only). semaglutide brands + class.
Ground truth: brands Ozempic, Wegovy, Rybelsus; class 'GLP-1 receptor agonists'.
Checks: nav /semaglutide | answer names >=2 brands + class | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, drug_brands, drug_class_name,
                        contains_any, count_present, llm_text_match, Judge, parse_args)

SLUG = "semaglutide"

def main():
    a = parse_args()
    j = Judge('Drugs.com--7', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    brands = drug_brands(ref, SLUG) or []; cls = drug_class_name(ref, SLUG)
    j.check("nav_drug", navigated_to(t, f"/{SLUG}"), "opened the semaglutide page")
    j.check("db_ground_truth", brands and cls is not None, f"brands={brands} class={cls!r}")
    j.check("answer_brands", brands and count_present(fa, brands) >= 2, f"brands={brands} final={fa!r}")
    j.check("answer_class", contains_any(fa, ["glp-1", "glp 1", "receptor agonist"]), f"class_gt={cls!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Brand names: {', '.join(brands)}. Drug class: {cls}.",
        "What brand names are listed for semaglutide, and what is its drug class?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
