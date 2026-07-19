#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--4.

Qualifying years on your National Insurance record usually needed for the FULL
new State Pension.
Ground truth: 35 qualifying years (on "The new State Pension" guidance page).
Note: 10 qualifying years is the minimum for ANY pension — the answer must be 35
for the FULL amount, so a bare "10" is wrong.

Checks: nav to the State Pension guidance page + answer states 35 (and not merely
10) + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_int,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/the-new-state-pension"
QUES = ("How many qualifying years on your National Insurance record do you usually "
        "need to get the full new State Pension?")

def main():
    a = parse_args()
    j = Judge('GOV.UK--4', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_state_pension", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_35_years", has_int(fa, 35), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "35 qualifying years", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
