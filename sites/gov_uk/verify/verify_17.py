#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--17.

Foreign travel advice guidance, and the organisation that provides it.
Ground truth: the Foreign, Commonwealth & Development Office (FCDO) — publisher of
"Foreign travel advice".

Checks: nav to the foreign-travel-advice page + answer names the FCDO +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/foreign-travel-advice"
QUES = "Find the foreign travel advice guidance and name the organisation that provides it."

def main():
    a = parse_args()
    j = Judge('GOV.UK--17', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_travel_advice", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_org",
            contains_any(fa, ["foreign, commonwealth", "fcdo",
                              "foreign, commonwealth & development office"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "Foreign, Commonwealth & Development Office (FCDO)", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
