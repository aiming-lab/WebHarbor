#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--13.

How to apply for or renew a Blue Badge for disabled people.
Ground truth: the "Apply for or renew a Blue Badge" guidance (apply online or via
your local council). Navigation task — reaching the page is the objective.

Checks: nav to the Blue Badge guidance page + answer references applying/renewing
a Blue Badge + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/apply-for-or-renew-a-blue-badge"
QUES = "Find how to apply for or renew a Blue Badge for disabled people."

def main():
    a = parse_args()
    j = Judge('GOV.UK--13', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_blue_badge", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    # Navigation task: reaching the page is the gate; the answer need only identify
    # the Blue Badge (how-to wording varies too much to match on).
    j.check("answer_blue_badge", contains_any(fa, ["blue badge"]), f"answer={fa!r}")
    ok, why = llm_text_match(
        fa, "Apply for or renew a Blue Badge online or through your local council", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
