#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--31.

Look up the use of modal verbs in the grammar section for expressing possibility and find examples of their usage in sentences.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/modal-verbs-possibility
  grammar-page DOM shows the topic ('Modal verbs: possibility') and its examples
  answer mentions: may, might, could
  answer contains: it may rain later today... (any of the shown 8)
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

TASK_ID = "Cambridge Dictionary--31"

NAV = "/grammar/british-grammar/modal-verbs-possibility"
TITLE = 'Modal verbs: possibility'
DOM_PROBE = 'It may rain later today.'
GT = "Modal verbs for possibility: may, might and could. May suggests a stronger possibility than might or could; all three are followed by the base form of the verb. Examples shown: It may rain later today. / She might come to the party, but she's not sure. / Could you be right? I think it's possible. / He may have forgotten about the meeting. / She might have taken the wrong train."
QUESTION = 'How are modal verbs may, might and could used to express possibility, with examples?'
SHOT_MUST = "the grammar page 'Modal verbs: possibility'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_modal_verbs", lambda t: (
            contains_all(final_answer(t), ['may', 'might', 'could']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_example", lambda t: (
            contains_any(final_answer(t), ['it may rain later today', 'she might come to the party', 'could you be right', 'he may have forgotten about the meeting', 'she might have taken the wrong train', 'the government may introduce new regulations', 'i might go out tonight', 'she could pass the exam']),
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
