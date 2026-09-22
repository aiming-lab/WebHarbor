#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--33.

Find explanations and examples of the passive voice in Grammar.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/passive-voice
  grammar-page DOM shows the topic ('Passive voice') and its examples
  answer contains: past participle... (any of the shown 3)
  answer contains at least 2 of the 8 example fragments shown
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

TASK_ID = "Cambridge Dictionary--33"

NAV = "/grammar/british-grammar/passive-voice"
TITLE = 'Passive voice'
DOM_PROBE = 'The letters are delivered every morning.'
GT = 'Passive voice: formed with the appropriate form of the verb be + the past participle; the agent may be included with by or omitted. Examples shown: The letters are delivered every morning. / The book was written in 1984. / The problem has been solved. / The project will be completed next week. / The Mona Lisa was painted by Leonardo da Vinci. / My car has been stolen.'
QUESTION = 'How is the passive voice formed and used, with examples?'
SHOT_MUST = "the grammar page 'Passive voice'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_formation_rule", lambda t: (
            contains_any(final_answer(t), ['past participle', 'form of the verb be', 'be + past']),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_examples", lambda t: (
            count_list_matches(final_answer(t), ['letters are delivered every morning', 'book was written in 1984', 'problem has been solved', 'project will be completed next week', 'mona lisa was painted by leonardo da vinci', 'my car has been stolen', 'it is believed that the company will announce new jobs', 'samples were heated to 100 degrees']) >= 2,
            f"answer matches={count_list_matches(final_answer(t), ['letters are delivered every morning', 'book was written in 1984', 'problem has been solved', 'project will be completed next week', 'mona lisa was painted by leonardo da vinci', 'my car has been stolen', 'it is believed that the company will announce new jobs', 'samples were heated to 100 degrees'])}")),
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
