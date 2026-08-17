#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--19.

Compare gregarious vs benevolent: which entered English earlier + POS of each.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /dictionary/gregarious AND /dictionary/benevolent | answer contains 'benevolent','15th century','1668','adjective' (deterministic) | LLM-anchored 'earlier' judgement
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
    j = Judge('Merriam-Webster--19', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_gregarious", navigated_to(t, "/dictionary/gregarious"),
            f"navigated={navigated_to(t, '/dictionary/gregarious')}")
    j.check("nav_benevolent", navigated_to(t, "/dictionary/benevolent"),
            f"navigated={navigated_to(t, '/dictionary/benevolent')}")
    j.check("answer_has_facts", contains_all(fa, ["benevolent", "15th century", "1668", "adjective"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa,
        "benevolent entered English earlier. benevolent: 15th century (adjective); gregarious: 1668 (adjective). Both are adjectives.",
        "Comparing gregarious and benevolent: which entered English earlier, and what part of speech is each?")
    j.check("answer_benevolent_earlier", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
