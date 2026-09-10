#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--1.

Look up ubiquitous; quote exact sense-1 definition.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /dictionary/ubiquitous | answer==sense1 text (deterministic norm-equal) | screenshot shows sense1
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, last_shot, shot_after_url,
                        contains_all, contains_any, answer_equals, extract_years,
                        extract_score, resolve_db, saved_words_for, user_exists,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Merriam-Webster--1', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_ubiquitous", navigated_to(t, "/dictionary/ubiquitous"),
            f"navigated={navigated_to(t, '/dictionary/ubiquitous')}")
    EXPECTED = "existing or being everywhere at the same time : constantly encountered : widespread"
    j.check("answer_sense1", answer_equals(fa, EXPECTED), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, EXPECTED, "first numbered definition of ubiquitous")
        j.check("screenshot_shows_sense1", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
