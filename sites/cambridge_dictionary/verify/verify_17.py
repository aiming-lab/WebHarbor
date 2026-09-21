#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--17.

How many meanings of unblemished the dictionary gives (count the senses on the entry page).

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/unblemished
  entry DOM shows the single definition
  answer states the number of meanings directly (one)
  LLM anchored answer match + entry screenshot
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

TASK_ID = "Cambridge Dictionary--17"

import re

NAV = "/dictionary/english/unblemished"
HEADWORD = "unblemished"
IPA_UK = r"""/ʌnˈblemɪʃt/"""
DEF_TEXT = "Not spoiled or damaged in any way; perfect."
GT = ("The Cambridge Dictionary entry for unblemished gives exactly ONE meaning "
      "(a single sense): Not spoiled or damaged in any way; perfect.")
QUESTION = "How many meanings of unblemished are given in the Cambridge Dictionary?"
SHOT_MUST = "the dictionary entry for unblemished with its IPA pronunciation"

def _count_ok(t):
    # the task explicitly says "give the number directly", so a bare number is a
    # complete answer; the count must be stated as 1 / one / single
    fa = fold(final_answer(t))
    return bool(re.search(r"(^|\W)(1|one|single)(\W|$)", fa))

def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_entry", lambda t: (
            fold(HEADWORD) in fold(observed_text_at(t, NAV))
            and ipa_contains(observed_text_at(t, NAV), IPA_UK),
            "entry DOM must show the headword and its IPA")),
        ("answer_states_count", lambda t: (
            _count_ok(t), f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_entry", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Cambridge Dictionary entry page for unblemished")
    return ok, ev, True


if __name__ == "__main__":
    main()
