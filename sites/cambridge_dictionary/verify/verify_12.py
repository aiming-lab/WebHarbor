#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--12.

Find the pronunciation, definition, and a sample sentence for the word "resilience" in the Cambridge Dictionary.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/resilience
  entry DOM shows headword + IPA
  answer contains the IPA notation as shown on the page
  answer contains the definition as shown on the page
  answer quotes an example sentence shown on the page
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

TASK_ID = "Cambridge Dictionary--12"

NAV = "/dictionary/english/resilience"
HEADWORD = "resilience"
IPA_UK = r"""/rɪˈzɪl.i.əns/"""
IPA_US = r"""/rɪˈzɪl.jəns/"""
DEF_ANY = ['happy, successful, etc. again after something difficult', 'return to its original form after being bent']
EX_ANY = ['remarkable resilience in the face of adversity', 'resilience was tested by the floods']
GT = 'resilience, noun [U], level C1. UK IPA: /rɪˈzɪl.i.əns/. US IPA: /rɪˈzɪl.jəns/. Sense 1: The ability to be happy, successful, etc. again after something difficult or bad has happened. Sense 2: The ability of a substance to return to its original form after being bent, stretched, or pressed. Sample sentence: She showed remarkable resilience in the face of adversity.'
QUESTION = 'What are the pronunciation, definition, and a sample sentence for the word resilience as shown in the Cambridge Dictionary?'
SHOT_MUST = 'the dictionary entry for resilience with its IPA pronunciation /rɪˈzɪl.i.əns/'


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
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_entry", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        f"the Cambridge Dictionary entry page for {HEADWORD}")
    return ok, ev, True


if __name__ == "__main__":
    main()
