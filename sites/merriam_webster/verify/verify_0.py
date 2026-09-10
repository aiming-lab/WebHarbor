#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--0.

Look up serendipity; report its MW respelling pronunciation.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /dictionary/serendipity | answer=respelling (LLM-anchored, phrasing varies) | screenshot shows pronunciation
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
    j = Judge('Merriam-Webster--0', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_serendipity", navigated_to(t, "/dictionary/serendipity"),
            f"navigated={navigated_to(t, '/dictionary/serendipity')}")
    # Deterministic answer check: the task explicitly asks for the respelling WITH its
    # accent marks as shown, so the leading secondary-stress ˌ + primary-stress ˈdi must
    # both appear. (An agent that drops the leading ˌ has not reported it 'as shown'.)
    j.check("answer_has_stress_marks", contains_all(fa, ["ˌser", "ˈdi", "pə", "tē"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "ˌser-ən-ˈdi-pə-tē",
        "What is the Merriam-Webster respelling pronunciation of serendipity?")
    j.check("answer_pronunciation", ok, ev, llm=True)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "\u02ccser-\u0259n-\u02c8di-p\u0259-t\u0113",
            "respelling pronunciation of serendipity")
        j.check("screenshot_shows_pron", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_pron", False, "no screenshots in run")
    j.emit()

if __name__ == "__main__":
    main()
