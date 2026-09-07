#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--13.

Games & Quizzes page: count quizzes + difficulty of each.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /games-quizzes | answer contains '3', 3 titles, 'easy', 'medium' (deterministic) | screenshot shows index
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
    j = Judge('Merriam-Webster--13', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_games", navigated_to(t, "/games-quizzes"),
            f"navigated={navigated_to(t, '/games-quizzes')}")
    NEED = ["3", "name that word", "synonym showdown", "opposites attract", "easy", "medium"]
    j.check("answer_count_and_levels", contains_all(fa, NEED), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Name That Word", "list of quizzes and their difficulty levels")
        j.check("screenshot_shows_index", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
