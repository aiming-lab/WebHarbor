#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--6.

Translation of sustainability into Chinese and French as shown in the dictionary.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/sustainability
  entry DOM shows the headword
  answer gives the Chinese translation (simplified or traditional) as shown
  answer gives the French translation as shown
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

TASK_ID = "Cambridge Dictionary--6"

NAV = "/dictionary/english/sustainability"
HEADWORD = "sustainability"
IPA_UK = r"""/səˌsteɪnəˈbɪlɪti/"""
GT = ("Translations of sustainability shown in the Cambridge Dictionary entry: "
      "Chinese 可持续性 (simplified; a traditional variant 可持續性 is also listed) and "
      "French durabilité. Reporting the Chinese translation 可持续性 and the French "
      "translation durabilité fully answers the question; the traditional variant is "
      "optional extra detail.")
QUESTION = "What is the translation of sustainability into Chinese and French given in the Cambridge Dictionary?"
SHOT_MUST = "the Cambridge Dictionary entry page for sustainability"

def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_entry", lambda t: (
            fold(HEADWORD) in fold(observed_text_at(t, NAV)),
            "entry DOM must show the headword")),
        ("answer_chinese_translation", lambda t: (
            contains_translation(final_answer(t), ["可持续性", "可持續性"]),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_french_translation", lambda t: (
            contains_translation(final_answer(t), ["durabilité"]),
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
        "the Cambridge Dictionary entry page for sustainability")
    return ok, ev, True


if __name__ == "__main__":
    main()
