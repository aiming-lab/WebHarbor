#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--2.

Deadline for filing an online Self Assessment tax return.
Ground truth: 31 January (following the end of the tax year) — stated on both the
"Self Assessment deadlines" and "File your Self Assessment tax return" pages.

Checks: nav to a Self Assessment guidance page + answer states 31 January +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, has_day_month,
                        llm_text_match, Judge, parse_args)

SLUGS = ["/guidance/self-assessment-deadlines",
         "/guidance/file-your-self-assessment-tax-return"]
QUES = "What is the deadline for filing an online Self Assessment tax return?"

def main():
    a = parse_args()
    j = Judge('GOV.UK--2', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_self_assessment", navigated_any(t, SLUGS), f"navigated_any={navigated_any(t, SLUGS)}")
    j.check("answer_deadline", has_day_month(fa, 31, "January"), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "31 January", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
