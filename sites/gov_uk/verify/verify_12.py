#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--12.

Guidance on applying for or renewing an adult passport, and the organisation
responsible for it.
Ground truth: His Majesty's Passport Office (HMPO) — publisher of the "Apply for
or renew an adult passport" guidance.

Checks: nav to the adult-passport guidance page + answer names the Passport
Office + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/apply-for-or-renew-an-adult-passport"
QUES = ("Use the search to find the guidance on applying for or renewing an adult "
        "passport, and identify which organisation is responsible for it.")

def main():
    a = parse_args()
    j = Judge('GOV.UK--12', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_passport_page", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_org", contains_any(fa, ["passport office", "hmpo"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "His Majesty's Passport Office (HMPO)", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
