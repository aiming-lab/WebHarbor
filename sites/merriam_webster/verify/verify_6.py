#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--6.

thesaurus calm; list every antonym.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /thesaurus/calm | answer contains all 8 antonyms (deterministic) | screenshot shows antonym list
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
    j = Judge('Merriam-Webster--6', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_thesaurus_calm", navigated_to(t, "/thesaurus/calm"),
            f"navigated={navigated_to(t, '/thesaurus/calm')}")
    ANT = ["angry", "turbulent", "restless", "agitated", "stormy", "unsettled", "rough", "tempestuous"]
    j.check("answer_all_8_antonyms", contains_all(fa, ANT), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, ", ".join(ANT), "antonyms of calm shown on the thesaurus page")
        j.check("screenshot_shows_antonyms", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
