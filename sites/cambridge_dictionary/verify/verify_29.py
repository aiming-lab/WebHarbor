#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--29.

Plus section: do the easy Animals image quiz and report the final score.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /plus/quiz/image-quiz-animals-easy
  final page DOM shows the quiz result panel
  answer reports a final score as N / 5
  vision check: result-panel score matches the reported score
Ground truth below was extracted from the live mirror pages and is frozen here.
Input/Output: see verify_lib.run_verifier / verify_lib.parse_args.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run_verifier, navigated_to, navigated_any, nav_urls, step_urls,
                        is_mirror_url, observed_text_at,
                        observed_texts, final_answer, action_texts,
                        action_results_text, contains_all, contains_any,
                        contains_any_folded_ci, contains_translation,
                        ipa_contains, count_list_matches,
                        extract_score, count_word_sentences, llm_text_match,
                        llm_screenshot_shows, shot_after_url, last_shot, fold)

TASK_ID = "Cambridge Dictionary--29"

QUIZ_NAVS = ['/plus/quiz/image-quiz-animals-easy']
QUIZ_NAME = 'Animals Image Quiz (Easy)'
TOTAL = 5

def _quiz_dom_completed(t):
    dom = " ".join(observed_texts(t))
    return ("quiz complete" in fold(dom)) and ("your score" in fold(dom))

def _score(t):
    return extract_score(final_answer(t), TOTAL)

def main():
    run_verifier(TASK_ID, [
        ("nav_quiz", lambda t: (navigated_to(t, "/plus/quiz/image-quiz-animals-easy"),
            "quiz=" + str([navigated_to(t, "/plus/quiz/image-quiz-animals-easy")]))),
        ("dom_quiz_completed", lambda t: (
            _quiz_dom_completed(t),
            "final page DOM must show the quiz result panel (Quiz Complete / Your score)")),
        ("answer_reports_score", lambda t: (
            _score(t) is not None, f"final={final_answer(t)[:150]!r}")),
        ("screenshot_shows_reported_score", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    score = extract_score(final_answer(t), TOTAL)
    if score is None:
        return False, "no score reported to cross-check", True
    ok, ev = llm_screenshot_shows(
        s, f"the quiz result panel showing 'Your score: {score} / {TOTAL}'",
        f"the final score of the {QUIZ_NAME} on the result panel")
    return ok, ev, True


if __name__ == "__main__":
    main()
