#!/usr/bin/env python3
"""Verifier for Drugs.com--10 (read-only). ibuprofen FAQ: OTC dose + 24h max.
Ground truth (FAQ): OTC 200-400 mg every 4-6 hours; do not exceed 1200 mg in 24 hours (OTC).
Checks: nav /ibuprofen | answer states 200(-400) mg + 1200 mg/24h | LLM anchor."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_number, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Drugs.com--10', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/ibuprofen"), "opened the ibuprofen page")
    # OTC dose 200-400 mg; accept 200 or 400. 24h max 1200 mg (OTC).
    j.check("answer_otc_dose", contains_number(fa, 200) or contains_number(fa, 400), f"final={fa!r}")
    j.check("answer_24h_max", contains_number(fa, 1200), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "OTC: 200-400 mg every 4-6 hours; do not exceed 1200 mg in 24 hours.",
        "According to the ibuprofen FAQ, what is the typical OTC dose and the maximum amount in 24 hours?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
