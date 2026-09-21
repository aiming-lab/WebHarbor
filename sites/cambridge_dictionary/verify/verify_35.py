#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--35.

Find the most common prepositions that consist of groups of words.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /grammar/british-grammar/group-prepositions
  grammar-page DOM shows the topic ('Group prepositions') and its examples
  answer contains at least 4 of the 8 example fragments shown
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

TASK_ID = "Cambridge Dictionary--35"

NAV = "/grammar/british-grammar/group-prepositions"
TITLE = 'Group prepositions'
DOM_PROBE = 'According to the report, profits have increased.'
GT = 'Group prepositions consist of more than one word and function as a single preposition; the most common ones consist of groups of words ending in a simple preposition. Examples shown: According to the report, profits have increased. / She succeeded because of her hard work. / In spite of the rain, the match continued. / We arrived in time for the start of the show. / On behalf of the entire team, I thank you. / He sat in front of the television all evening. / With regard to your question, I have no comment. / In addition to her salary, she receives a bonus.'
QUESTION = 'Which group prepositions (prepositions that consist of groups of words) does the Cambridge Dictionary grammar page present? Listing the group prepositions themselves answers the question; example sentences from the page are optional additional detail.'
SHOT_MUST = "the grammar page 'Group prepositions'"

def main():
    run_verifier(TASK_ID, [
        ("nav_grammar_page", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_topic", lambda t: (
            fold(TITLE) in fold(observed_text_at(t, NAV))
            and fold(DOM_PROBE) in fold(observed_text_at(t, NAV)),
            "grammar-page DOM must show the topic and its examples")),

        ("answer_group_prepositions", lambda t: (
            count_list_matches(final_answer(t), ['according to', 'because of', 'in spite of', 'in time for', 'on behalf of', 'in front of', 'with regard to', 'in addition to']) >= 4,
            f"answer matches={count_list_matches(final_answer(t), ['according to', 'because of', 'in spite of', 'in time for', 'on behalf of', 'in front of', 'with regard to', 'in addition to'])}")),
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
