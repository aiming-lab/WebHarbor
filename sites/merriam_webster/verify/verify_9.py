#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--9.

Word of the Day featured word + part of speech (deterministic, pinned).

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /word-of-the-day | answer contains 'ambivalent' AND 'adjective' (deterministic) | screenshot shows ambivalent adjective
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
    j = Judge('Merriam-Webster--9', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_wotd", navigated_to(t, "/word-of-the-day"),
            f"navigated={navigated_to(t, '/word-of-the-day')}")
    j.check("answer_word_pos", contains_all(fa, ["ambivalent", "adjective"]), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "ambivalent", "featured word of the day and its part of speech")
        j.check("screenshot_shows_wotd", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
