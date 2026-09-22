#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--37.

Understand the use of articles ('a', 'an', 'the') in English Grammar, including examples with both countable and uncountable nouns.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/articles
  grammar-page DOM shows the topic ('Articles: 'a', 'an' and 'the'') and its examples
  answer contains at least 3 of the 8 example fragments shown
  answer mentions: countable, uncountable
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

TASK_ID = "Cambridge Dictionary--37"

NAV = "/grammar/british-grammar/articles"
TITLE = "Articles: 'a', 'an' and 'the'"
DOM_PROBE = 'I saw a dog in the park.'
GT = "Articles: 'a'/'an' are indefinite articles used with singular countable nouns (a before consonant sounds, an before vowel sounds); 'the' is the definite article used when the thing is identified; zero article for general plurals and uncountable nouns. Examples shown: I saw a dog in the park. / He is an honest man. (an + silent h) / The sun rises in the east. / Dogs make great pets. / Water is essential for life. / The water in this lake is very cold."
QUESTION = 'How are the articles a, an and the used with countable and uncountable nouns, with examples?'
SHOT_MUST = "the grammar page 'Articles: 'a', 'an' and 'the''"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_examples", lambda t: (
            count_list_matches(final_answer(t), ['i saw a dog in the park', 'he is an honest man', 'the sun rises in the east', 'dogs make great pets', 'water is essential for life', 'she bought a university degree', 'the dog was very friendly', 'she is the best student in the class']) >= 3,
            f"answer matches={count_list_matches(final_answer(t), ['i saw a dog in the park', 'he is an honest man', 'the sun rises in the east', 'dogs make great pets', 'water is essential for life', 'she bought a university degree', 'the dog was very friendly', 'she is the best student in the class'])}")),
        ("answer_countable_uncountable", lambda t: (
            contains_all(final_answer(t), ['countable', 'uncountable']),
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
