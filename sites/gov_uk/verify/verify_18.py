#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--18.

Browse the Childcare and parenting topic and find the guidance on Child Benefit
eligibility.
Ground truth: the "Child Benefit: eligibility" guidance (child under 16, or under
20 in approved education/training), reached by browsing the Childcare topic.

Checks: nav to the Child Benefit eligibility page (primary) — with the childcare
browse path as supporting evidence — + answer references Child Benefit
eligibility + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/child-benefit-eligibility"
QUES = "Browse the Childcare and parenting topic and find the guidance on Child Benefit eligibility."

def main():
    a = parse_args()
    j = Judge('GOV.UK--18', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_child_benefit", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    # Non-gating: record whether the agent reached it via the Childcare topic browse.
    j.evidence.append(f"[INFO] browsed_childcare={navigated_to(t, '/browse/childcare')}")
    j.check("answer_child_benefit",
            contains_any(fa, ["child benefit"]) and
            contains_any(fa, ["under 16", "approved education", "eligib"]), f"answer={fa!r}")
    ok, why = llm_text_match(
        fa, "Child Benefit eligibility: a child under 16 (or under 20 in approved education/training)", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
