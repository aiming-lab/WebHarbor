#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--23.

Find the US English pronunciation of the word "meticulous" and the IPA notation, then one example sentence.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/meticulous
  entry DOM shows headword + IPA
  answer contains the IPA notation as shown on the page
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

TASK_ID = "Cambridge Dictionary--23"

NAV = "/dictionary/english/meticulous"
HEADWORD = "meticulous"
IPA_UK = r"""/məˈtɪkjələs/"""
DEF_ANY = ['very careful and with great attention to every detail']
EX_ANY = ['kept meticulous records of all expenses', 'meticulous attention to detail makes him an excellent surgeon']
GT = 'meticulous, adjective, level C1. US IPA: /məˈtɪkjələs/ (UK identical). Definition: Very careful and with great attention to every detail. Example: She kept meticulous records of all expenses.'
QUESTION = 'What is the US English IPA pronunciation of meticulous and one example sentence provided by the dictionary?'
SHOT_MUST = 'the dictionary entry for meticulous with its IPA pronunciation /məˈtɪkjələs/'


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
