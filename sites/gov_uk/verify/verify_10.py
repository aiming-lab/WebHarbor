#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--10.

Most recently published announcement on GOV.UK, and a summary of it.
Ground truth: "Spring Statement update on growth measures" (HM Treasury, dated
28 March 2025 — the newest by published_at; it heads both the homepage "Latest
announcements" list and /government/announcements). The answer is a synthetic
on-site title, so it cannot be recalled without navigating.

Checks: nav to the announcements listing (or homepage feed) + answer names the
Spring Statement / growth-measures story + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

NAV = ["/government/announcements", "/government/organisations/hm-treasury"]
QUES = "Find the most recently published announcement on GOV.UK and summarise what it is about."

def main():
    a = parse_args()
    j = Judge('GOV.UK--10', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_announcements", navigated_any(t, NAV), f"navigated_any={navigated_any(t, NAV)}")
    # "spring statement" / "growth plan" are unique to this story; "growth measures"
    # is NOT (it also appears in the older Autumn Budget announcement), so it is excluded.
    j.check("answer_names_story",
            contains_any(fa, ["spring statement", "growth plan"]),
            f"answer={fa!r}")
    ok, why = llm_text_match(
        fa, "Spring Statement update on growth measures — the Chancellor's next steps on the growth plan", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
