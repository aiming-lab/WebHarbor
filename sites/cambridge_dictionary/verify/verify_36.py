#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--36.

Search for guidelines on using indirect speech, with examples of how to change direct speech to indirect speech.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/indirect-speech
  grammar-page DOM shows the topic ('Indirect speech') and its examples
  answer contains at least 2 of the 6 example fragments shown
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

TASK_ID = "Cambridge Dictionary--36"

NAV = "/grammar/british-grammar/indirect-speech"
TITLE = 'Indirect speech'
DOM_PROBE = 'She said that she was tired.'
GT = 'Indirect speech reports what someone said without their exact words; tenses are usually backshifted and pronouns/time expressions change. Examples shown: Direct: "I am tired." -> Indirect: She said that she was tired. / Direct: "We left early." -> Indirect: They said they had left early. / Direct: "I will call you." -> Indirect: He said he would call me. / Direct: "Are you coming?" -> Indirect: She asked if I was coming. / Direct: "Where do you live?" -> Indirect: He asked me where I lived.'
QUESTION = 'How is direct speech changed into indirect speech, with examples?'
SHOT_MUST = "the grammar page 'Indirect speech'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_examples", lambda t: (
            count_list_matches(final_answer(t), ['she said that she was tired', 'they said they had left early', 'he said he would call me', 'she asked if i was coming', 'he asked me where i lived', 'she wanted to know what time the film started']) >= 2,
            f"answer matches={count_list_matches(final_answer(t), ['she said that she was tired', 'they said they had left early', 'he said he would call me', 'she asked if i was coming', 'he asked me where i lived', 'she wanted to know what time the film started'])}")),
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
