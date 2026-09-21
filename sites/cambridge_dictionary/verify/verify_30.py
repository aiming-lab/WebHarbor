#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--30.

Find the grammar for present perfect simple uses, including examples of affirmative, negative, and interrogative sentences.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/present-perfect-simple
  grammar-page DOM shows the topic ('Present perfect simple') and its examples
  answer contains: have visited paris three times... (any of the shown 2)
  answer contains: havent seen him since last monday... (any of the shown 2)
  answer contains: have you ever eaten sushi... (any of the shown 2)
  answer contains: have/has... (any of the shown 6)
  LLM anchored answer match + grammar-page screenshot
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

TASK_ID = "Cambridge Dictionary--30"

NAV = "/grammar/british-grammar/present-perfect-simple"
TITLE = 'Present perfect simple'
DOM_PROBE = 'I have visited Paris three times.'
GT = "Present perfect simple: used for past events with a connection to the present; formed with have/has + past participle. Examples shown: Affirmative: I have visited Paris three times. / She has already finished her homework. Negative: I haven't seen him since last Monday. / They haven't arrived yet. Interrogative: Have you ever eaten sushi? / Has she called back yet?"
QUESTION = 'What are the uses of the present perfect simple with affirmative, negative and interrogative examples?'
SHOT_MUST = "the grammar page 'Present perfect simple'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_affirmative_example", lambda t: (
            contains_any(final_answer(t), ['have visited paris three times', 'has already finished her homework']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_negative_example", lambda t: (
            contains_any(final_answer(t), ['havent seen him since last monday', 'havent arrived yet']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_interrogative_example", lambda t: (
            contains_any(final_answer(t), ['have you ever eaten sushi', 'has she called back yet']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_formation_rule", lambda t: (
            contains_any(final_answer(t), ['have/has', 'have or has', 'has + past participle', 'have + past participle', 'formed with have', 'have or has + past']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_topic", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Cambridge Grammar page for the topic")
    return ok, ev, True


if __name__ == "__main__":
    main()
