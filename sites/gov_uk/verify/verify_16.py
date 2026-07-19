#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--16.

How to register to vote in the UK.
Ground truth: the "Register to vote" service (takes ~5 minutes; you need your
National Insurance number). Navigation task — reaching the page is the objective.

Checks: nav to the register-to-vote page + answer references registering to vote +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/register-to-vote"
QUES = "Find out how to register to vote in the UK."

def main():
    a = parse_args()
    j = Judge('GOV.UK--16', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_register_to_vote", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_register",
            contains_any(fa, ["register to vote", "national insurance"]), f"answer={fa!r}")
    ok, why = llm_text_match(
        fa, "Use the 'Register to vote' service (needs your National Insurance number)", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
