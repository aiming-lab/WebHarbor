#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--14.

Skilled Worker visa guidance page, and which department publishes it.
Ground truth: Home Office — publisher of the "Skilled Worker visa" guidance.

Checks: nav to the Skilled Worker visa guidance page + answer names the Home
Office + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/skilled-worker-visa"
QUES = "Find the guidance page for the Skilled Worker visa and identify which department publishes it."

def main():
    a = parse_args()
    j = Judge('GOV.UK--14', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_skilled_worker", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_department", contains_all(fa, ["home office"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "Home Office", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
