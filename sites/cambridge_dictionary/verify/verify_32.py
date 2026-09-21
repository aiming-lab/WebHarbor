#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--32.

Search for the differences between "fewer" and "less" in the grammar section, and provide examples illustrating their correct usage.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/fewer-and-less
  grammar-page DOM shows the topic ('Fewer and less') and its examples
  answer contains: fewer cars on the road today... (any of the shown 3)
  answer contains: less water to protect the environment... (any of the shown 3)
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

TASK_ID = "Cambridge Dictionary--32"

NAV = "/grammar/british-grammar/fewer-and-less"
TITLE = 'Fewer and less'
DOM_PROBE = 'There are fewer cars on the road today.'
GT = "Fewer vs less: 'fewer' is used before plural countable nouns; 'less' is used before uncountable nouns and before numbers and amounts. Examples shown: There are fewer cars on the road today. / Fewer students attended the lecture than expected. / We should use less water to protect the environment. / There is less traffic on Sundays. / The journey takes less than an hour."
QUESTION = 'What is the difference between fewer and less, with examples of correct usage?'
SHOT_MUST = "the grammar page 'Fewer and less'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_fewer_example", lambda t: (
            contains_any(final_answer(t), ['fewer cars on the road today', 'fewer students attended the lecture', 'fewer meetings and more action']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_less_example", lambda t: (
            contains_any(final_answer(t), ['less water to protect the environment', 'less traffic on sundays', 'journey takes less than an hour']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_rule_countable_uncountable", lambda t: (
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
