#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--9.

Year HM Treasury was established, from its organisation page.
Ground truth: 1066 (as recorded on the HM Treasury organisation page).

Checks: nav to the HM Treasury organisation page + answer states 1066 +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, has_int,
                        llm_text_match, Judge, parse_args)

SLUG = "/government/organisations/hm-treasury"
QUES = "Go to the HM Treasury organisation page and find the year it was established."

def main():
    a = parse_args()
    j = Judge('GOV.UK--9', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_treasury_org", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_established", has_int(fa, 1066), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "1066", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
