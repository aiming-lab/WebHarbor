#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--11.

HMRC news story reporting how many Self Assessment returns were filed on time,
and the figure.
Ground truth: 11.5 million ("Self Assessment: 11.5 million returns filed on
time", HMRC news story).

Checks: nav to the announcements listing (or HMRC org page) + answer states
11.5 million + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

NAV = ["/government/announcements", "/government/organisations/hm-revenue-customs"]
QUES = ("Find the HMRC news story that reports how many Self Assessment returns were "
        "filed on time, and state the figure.")

def main():
    a = parse_args()
    j = Judge('GOV.UK--11', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_announcements", navigated_any(t, NAV), f"navigated_any={navigated_any(t, NAV)}")
    j.check("answer_figure", contains_any(fa, ["11.5 million", "11,500,000"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "11.5 million Self Assessment returns filed on time", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
