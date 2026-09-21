#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--13.

One word, one phrase and one idiom related to euphoria (SMART Vocabulary on the entry page).

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/euphoria
  entry DOM shows the related word/phrase/idiom
  answer names the related word, phrase and idiom shown on the page
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

TASK_ID = "Cambridge Dictionary--13"

NAV = "/dictionary/english/euphoria"
HEADWORD = "euphoria"
IPA_UK = r"""/juːˈfɔːriə/"""
RELATED = ["euphoric", "sense of euphoria", "on cloud nine"]
GT = ("Words and phrases related to euphoria shown in the entry's SMART Vocabulary: "
      "related word 'euphoric', related phrase 'sense of euphoria', idiom 'on cloud nine'.")
QUESTION = "Which one word, one phrase and one idiom related to euphoria does the Cambridge Dictionary show?"
SHOT_MUST = "the dictionary entry for euphoria with its IPA pronunciation"

def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_related", lambda t: (
            count_list_matches(" ".join(observed_texts(t)), RELATED) >= 3,
            "entry DOM must show the related word, phrase and idiom")),
        ("answer_word_phrase_idiom", lambda t: (
            contains_all(final_answer(t), RELATED),
            f"final={final_answer(t)[:150]!r}")),
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
        "the Cambridge Dictionary entry page for euphoria")
    return ok, ev, True


if __name__ == "__main__":
    main()
