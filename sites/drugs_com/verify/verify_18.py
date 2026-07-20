#!/usr/bin/env python3
"""Verifier for Drugs.com--18 (read-only). amoxicillin adult dosing frequency.
Ground truth (dosage): 250 mg or 500 mg every 8 hours (i.e. three times daily) for standard
infections. Accept 'every 8 hours' / 'three times a day' / 'q8h'.
Checks: nav /amoxicillin | answer states the every-8-hours dosing | LLM anchor."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, drug_field,
                        contains_any, llm_text_match, Judge, parse_args)

SLUG = "amoxicillin"

def main():
    a = parse_args()
    j = Judge('Drugs.com--18', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    dosage = drug_field(ref, SLUG, "dosage")
    j.check("nav_drug", navigated_to(t, f"/{SLUG}"), "opened the amoxicillin page")
    j.check("db_ground_truth", dosage is not None and "every 8 hours" in (dosage or "").lower(), f"has_q8h={dosage is not None}")
    j.check("answer_frequency",
            contains_any(fa, ["every 8 hours", "8 hours", "three times", "3 times", "q8h", "tid"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Standard adult dosing is every 8 hours (three times daily).",
        "What is the typical adult dosing frequency for amoxicillin for standard infections?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
