#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--7.

thesaurus difficult; synonyms starting with C.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /thesaurus/difficult | answer contains 'challenging' AND 'complicated' (deterministic) | screenshot shows thesaurus
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
    j = Judge('Merriam-Webster--7', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_thesaurus_difficult", navigated_to(t, "/thesaurus/difficult"),
            f"navigated={navigated_to(t, '/thesaurus/difficult')}")
    j.check("answer_C_synonyms", contains_all(fa, ["challenging", "complicated"]), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "challenging", "synonyms of difficult, esp. ones starting with C")
        j.check("screenshot_shows_thesaurus", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
