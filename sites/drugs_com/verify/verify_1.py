#!/usr/bin/env python3
"""Verifier for Drugs.com--1 (read-only). metformin availability + CSA schedule.
Ground truth: availability 'Rx'; csa 'Not a controlled drug'.
Checks: nav /metformin | answer states availability (Rx) + not-controlled | DB anchor | LLM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, resolve_db,
                        drug_field, contains_any, Judge, parse_args, llm_text_match)

SLUG = "metformin"

def main():
    a = parse_args()
    j = Judge('Drugs.com--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    avail = drug_field(ref, SLUG, "availability"); csa = drug_field(ref, SLUG, "csa_schedule")
    j.check("nav_drug", navigated_any(t, [f"/{SLUG}", "/search"]), "reached metformin via search/detail")
    j.check("nav_detail", navigated_to(t, f"/{SLUG}"), "opened the metformin detail page")
    j.check("db_ground_truth", avail is not None and csa is not None, f"avail={avail!r} csa={csa!r}")
    j.check("answer_availability", contains_any(fa, ["rx", "prescription"]), f"final={fa!r}")
    j.check("answer_csa", contains_any(fa, ["not a controlled", "not controlled", "no schedule", "not scheduled", "no csa schedule", "not a scheduled"]),
            f"csa_gt={csa!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Availability: {avail}. CSA schedule: {csa}.",
        "What is metformin's availability (Rx/OTC/both) and CSA schedule?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
