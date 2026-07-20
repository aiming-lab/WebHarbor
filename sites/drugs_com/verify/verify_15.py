#!/usr/bin/env python3
"""Verifier for Drugs.com--15 (read-only). lisinopril pregnancy warning + availability.
Ground truth: BLACK BOX fetal-toxicity / Pregnancy Category D (discontinue in pregnancy);
availability 'Rx'.
Checks: nav /lisinopril | answer states pregnancy/fetal risk + Rx | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, drug_field,
                        contains_any, llm_text_match, Judge, parse_args)

SLUG = "lisinopril"

def main():
    a = parse_args()
    j = Judge('Drugs.com--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    warnings = drug_field(ref, SLUG, "warnings"); avail = drug_field(ref, SLUG, "availability")
    j.check("nav_drug", navigated_to(t, f"/{SLUG}"), "opened the lisinopril page")
    j.check("db_ground_truth", warnings is not None and avail is not None, f"avail={avail!r}")
    j.check("answer_pregnancy", contains_any(fa, ["pregnan", "fetal", "category d", "fetus", "birth"]), f"final={fa!r}")
    j.check("answer_availability", contains_any(fa, ["rx", "prescription"]), f"avail_gt={avail!r} final={fa!r}")
    ok, ev = llm_text_match(fa, "Pregnancy: black-box fetal toxicity — discontinue when pregnancy is detected "
                                f"(Category D). Availability: {avail}.",
        "What warnings are listed about pregnancy for lisinopril, and what is its availability?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
