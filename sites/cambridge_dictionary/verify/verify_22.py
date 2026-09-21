#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--22.

Use the Cambridge Dictionary to find the definition, UK pronunciation, and an example sentence for the word "quintessential."

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/quintessential
  entry DOM shows headword + IPA
  answer contains the IPA notation as shown on the page
  answer contains the definition as shown on the page
  answer quotes an example sentence shown on the page
  entry DOM contains the exact rendered IPA string (deterministic; the vision check was removed — the grading model misreads the small IPA stress marks at screenshot resolution, acceptor discrepancy 2)
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

TASK_ID = "Cambridge Dictionary--22"

NAV = "/dictionary/english/quintessential"
HEADWORD = "quintessential"
IPA_UK = r"""/ˌkwɪntɪˈsenʃəl/"""
DEF_ANY = ['most perfect or typical example of something']
EX_ANY = ['quintessential english gentleman', 'quintessential example of victorian architecture']
GT = 'quintessential, adjective, level C2, formal. UK IPA: /ˌkwɪntɪˈsenʃəl/. Definition: Representing the most perfect or typical example of something. Example: He is the quintessential English gentleman.'
QUESTION = 'What are the definition, UK pronunciation, and an example sentence for the word quintessential as shown in the Cambridge Dictionary?'
SHOT_MUST = 'the dictionary entry for quintessential with its IPA pronunciation /ˌkwɪntɪˈsenʃəl/'


def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV),
                                 f"nav={navigated_to(t, NAV)}")),
        ("page_shows_entry", lambda t: (
            fold(HEADWORD) in fold(observed_text_at(t, NAV))
            and ipa_contains(observed_text_at(t, NAV), IPA_UK),
            "entry DOM must show the headword and its IPA")),
        ("answer_pronunciation", lambda t: (
            ipa_contains(final_answer(t), IPA_UK),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_definition", lambda t: (
            contains_any(final_answer(t), DEF_ANY),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_example", lambda t: (
            contains_any(final_answer(t), EX_ANY),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),        ("page_shows_ipa_dom", lambda t: (
            '/ˌkwɪntɪˈsenʃəl/' in observed_text_at(t, NAV),
            "entry DOM must contain the exact rendered IPA string")),
    ])


if __name__ == "__main__":
    main()
