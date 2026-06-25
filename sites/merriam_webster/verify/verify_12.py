#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--12.

Synonym Showdown quiz: answer all + report final score.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /quiz/synonym-showdown + reached /submit | reported score X/10 (deterministic) | result screenshot shows matching score
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
    j = Judge('Merriam-Webster--12', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_quiz", navigated_to(t, "/quiz/synonym-showdown"),
            f"navigated={navigated_to(t, '/quiz/synonym-showdown')}")
    j.check("reached_result_page", navigated_to(t, "/quiz/synonym-showdown/submit"),
            f"navigated_submit={navigated_to(t, '/quiz/synonym-showdown/submit')}")
    score = extract_score(fa)
    j.check("reported_score_X_over_10", score is not None, f"final={fa!r}")
    s = shot_after_url(t, "/quiz/synonym-showdown/submit") or last_shot(t)
    if s and score is not None:
        ok, ev = llm_screenshot_shows(s, "Your Score " + score + " / 10",
            "the agent's final quiz score on the result page")
        j.check("screenshot_shows_reported_score", ok, ev, llm=True)
    elif s:
        ok, ev = llm_screenshot_shows(s, "Your Score", "quiz result page score")
        j.check("screenshot_shows_score_page", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_score_page", False, "no screenshots in run")

    j.emit()

if __name__ == "__main__":
    main()
