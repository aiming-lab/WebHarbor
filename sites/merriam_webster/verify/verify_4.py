#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--4.

meticulous first-known-use year.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /dictionary/meticulous | answer year==1827 (deterministic) | screenshot shows 1827
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
    j = Judge('Merriam-Webster--4', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_meticulous", navigated_to(t, "/dictionary/meticulous"),
            f"navigated={navigated_to(t, '/dictionary/meticulous')}")
    yrs = extract_years(fa)
    j.check("answer_year_1827", "1827" in yrs, f"years_found={yrs} final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "First Known Use: 1827",
            "first known use year of meticulous")
        j.check("screenshot_shows_1827", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
