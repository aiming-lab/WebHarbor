#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--39.

Plus section Word Scramble: unscramble the first example and spell the word.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /plus/word-scramble
  agent typed the target word into the scramble input
  page DOM shows the correct-answer feedback
  answer names the unscrambled word
  LLM anchored answer match + screenshot
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

TASK_ID = "Cambridge Dictionary--39"

NAV = "/plus/word-scramble"
TARGET = "theme"
SCRAMBLED = "MHEET"
GT = ("The first Word Scramble example shows the scrambled letters M H E E T with the clue "
      "'The subject matter of a conversation or discussion.'; the word is 'theme' and the "
      "game accepts it with the feedback 'Correct! Well done!'.")
QUESTION = "What word do the scrambled letters of the first Word Scramble example spell?"
SHOT_MUST = ("the Word Scramble game area with the answer 'theme' typed in the input "
             "box and the green feedback line 'Correct! Well done!' (with the party "
             "emoji) rendered below it")

def _typed_target(t):
    return any(fold(x) == fold(TARGET) for x in action_texts(t))

def main():
    run_verifier(TASK_ID, [
        ("nav_scramble", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("typed_target_word", lambda t: (
            _typed_target(t), f"typed={action_texts(t)!r}")),
        ("dom_shows_correct_feedback", lambda t: (
            "well done" in fold(observed_text_at(t, NAV)),
            "scramble page DOM must show the correct-answer feedback")),
        ("answer_names_word", lambda t: (
            fold(TARGET) in fold(final_answer(t)), f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_feedback", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    # the typed answer and the correct-answer feedback are visible only in the
    # final page state, so anchor on the last screenshot
    s = last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Word Scramble game page after a correct answer")
    return ok, ev, True


if __name__ == "__main__":
    main()
