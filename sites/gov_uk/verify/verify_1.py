#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--1.

Find the full weekly amount of the new State Pension.
Ground truth: £221.20 per week (on "The new State Pension" guidance page body).

Checks: nav to the State Pension guidance page + answer states £221.20 +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_money,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/the-new-state-pension"
QUES = "Find out the full weekly amount of the new State Pension."

def main():
    a = parse_args()
    j = Judge('GOV.UK--1', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_state_pension", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_amount", has_money(fa, "£221.20"), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "£221.20 per week", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
