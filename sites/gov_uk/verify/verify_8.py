#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--8.

How many people the Department for Work and Pensions employs.
Ground truth: 82,000 (on the DWP organisation page). A page-specific synthetic
figure, so recall alone cannot produce it.

Checks: nav to the DWP organisation page + answer states 82,000 +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_int,
                        llm_text_match, Judge, parse_args)

SLUG = "/government/organisations/dwp"
QUES = "Find out how many people the Department for Work and Pensions employs."

def main():
    a = parse_args()
    j = Judge('GOV.UK--8', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_dwp_org", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_employees", has_int(fa, 82000), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "82,000 employees", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
