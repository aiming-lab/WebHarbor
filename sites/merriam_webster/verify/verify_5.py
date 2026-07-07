#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--5.

thesaurus brave; list every synonym.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /thesaurus/brave | answer contains all 8 synonyms (deterministic) | screenshot shows synonym list
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
    j = Judge('Merriam-Webster--5', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_thesaurus_brave", navigated_to(t, "/thesaurus/brave"),
            f"navigated={navigated_to(t, '/thesaurus/brave')}")
    SYN = ["courageous", "fearless", "valiant", "heroic", "gallant", "bold", "adventurous", "intrepid"]
    j.check("answer_all_8_synonyms", contains_all(fa, SYN), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, ", ".join(SYN), "synonyms of brave shown on the thesaurus page")
        j.check("screenshot_shows_synonyms", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
