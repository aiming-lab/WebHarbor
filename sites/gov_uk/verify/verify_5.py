#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--5.

Penalty for filing your Self Assessment tax return one day late.
Ground truth: £100 (initial fixed penalty, on "Self Assessment deadlines").

Checks: nav to the Self Assessment deadlines page + answer states £100 +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_money,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/self-assessment-deadlines"
QUES = "Find out the penalty for filing your Self Assessment tax return one day late."

def main():
    a = parse_args()
    j = Judge('GOV.UK--5', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_sa_deadlines", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_penalty", has_money(fa, "£100"), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "£100", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
