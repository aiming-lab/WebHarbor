#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--34.

Understand the rules for forming and using comparative and superlative adjectives, including example sentences.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/comparative-and-superlative-adjectives
  grammar-page DOM shows the topic ('Comparative and superlative adjectives') and its examples
  answer contains: this road is longer than the other one... (any of the shown 4)
  answer contains: this is the tallest building in the city... (any of the shown 4)
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

TASK_ID = "Cambridge Dictionary--34"

NAV = "/grammar/british-grammar/comparative-and-superlative-adjectives"
TITLE = 'Comparative and superlative adjectives'
DOM_PROBE = 'This road is longer than the other one.'
GT = 'Comparative and superlative adjectives: for short adjectives add -er / -est; for longer adjectives use more / the most; irregular: good-better-best, bad-worse-worst, far-further/farther. Examples shown: This road is longer than the other one. / This solution is more efficient than the old one. / She is better at maths than her sister. / This is the tallest building in the city. / She is the most talented student in the class. / That was the worst film I have ever seen.'
QUESTION = 'What are the rules for forming and using comparative and superlative adjectives, with example sentences?'
SHOT_MUST = "the grammar page 'Comparative and superlative adjectives'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_comparative_example", lambda t: (
            contains_any(final_answer(t), ['this road is longer than the other one', 'solution is more efficient than the old one', 'she is better at maths than her sister', 'new model is much faster than the old one']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_superlative_example", lambda t: (
            contains_any(final_answer(t), ['this is the tallest building in the city', 'she is the most talented student in the class', 'that was the worst film i have ever seen', 'of all the options, this is the most suitable']),
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
