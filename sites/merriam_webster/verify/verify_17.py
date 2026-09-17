#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--17.

Compare empathy/nostalgia/optimism: which has most recent first-known-use.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav all 3 /dictionary/{empathy,nostalgia,optimism} | answer contains 'empathy' + years 1909,1756,1759 (deterministic) | LLM-anchored 'most recent' judgement
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
    j = Judge('Merriam-Webster--17', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    for w in ["empathy", "nostalgia", "optimism"]:
        j.check(f"nav_{w}", navigated_to(t, "/dictionary/" + w),
                f"navigated={navigated_to(t, '/dictionary/' + w)}")
    j.check("answer_has_3_years", contains_all(fa, ["1909", "1756", "1759"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa,
        "empathy is the most recent. empathy: 1909; nostalgia: 1756; optimism: 1759.",
        "Among empathy, nostalgia, optimism, which has the most recent first known use (report all 3 years)?")
    j.check("answer_most_recent_empathy", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
