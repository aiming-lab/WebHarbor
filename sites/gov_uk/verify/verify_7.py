#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--7.

Name of the minister responsible for HM Revenue & Customs.
Ground truth: Rt Hon James Murray MP (Exchequer Secretary) — on the HMRC
organisation page. This is a page-specific fact (not the department head), so it
resists knowledge-shortcut.

Checks: nav to the HMRC organisation page + answer names James Murray +
anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        llm_text_match, Judge, parse_args)

SLUG = "/government/organisations/hm-revenue-customs"
QUES = "Find the name of the minister responsible for HM Revenue & Customs."

def main():
    a = parse_args()
    j = Judge('GOV.UK--7', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_hmrc_org", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_minister", contains_all(fa, ["James Murray"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "Rt Hon James Murray MP (Exchequer Secretary)", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
