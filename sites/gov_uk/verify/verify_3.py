#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--3.

Standard rate of VAT that applies to most goods and services.
Ground truth: 20% (on the "VAT rates" guidance page body).

Checks: nav to the VAT rates guidance page + answer states 20% +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_percent,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/vat-rates"
QUES = "Find the standard rate of VAT that applies to most goods and services."

def main():
    a = parse_args()
    j = Judge('GOV.UK--3', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_vat_rates", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_rate", has_percent(fa, 20), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "20%", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
