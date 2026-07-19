#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--19.

NHS England news story about the NHS App, and how many users it has reached.
Ground truth: 30 million ("NHS App reaches 30 million users", NHS England news
story).

Checks: nav to the announcements listing (or NHS England org page) + answer states
30 million + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

NAV = ["/government/announcements", "/government/organisations/nhs-england"]
QUES = ("Find the NHS England news story about the NHS App and state how many users "
        "it has reached.")

def main():
    a = parse_args()
    j = Judge('GOV.UK--19', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_announcements", navigated_any(t, NAV), f"navigated_any={navigated_any(t, NAV)}")
    j.check("answer_users", contains_any(fa, ["30 million", "30,000,000"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "30 million NHS App users", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
