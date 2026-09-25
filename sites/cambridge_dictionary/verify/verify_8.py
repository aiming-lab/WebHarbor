#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--8.

Three different meanings of dog as given in the dictionary entry.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/dog
  entry DOM shows headword + IPA
  answer covers all three senses (animal / unpleasant person / follow)
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

TASK_ID = "Cambridge Dictionary--8"

NAV = "/dictionary/english/dog"
HEADWORD = "dog"
IPA_UK = r"""/dɒɡ/"""
GT = ("dog, noun/verb, level A1. UK IPA /dɒɡ/, US IPA /dɑːɡ/. Three meanings: "
      "1. [C] A common animal with four legs, kept as a pet or trained to do special jobs. "
      "2. [C] An unattractive or unpleasant person (informal, offensive). "
      "3. [T] To follow someone closely and persistently.")
QUESTION = "What three different meanings of dog does the Cambridge Dictionary give?"
SHOT_MUST = "the dictionary entry for dog with its IPA pronunciation"

def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_entry", lambda t: (
            fold(HEADWORD) in fold(observed_text_at(t, NAV))
            and ipa_contains(observed_text_at(t, NAV), IPA_UK),
            "entry DOM must show the headword and its IPA")),
        ("answer_covers_three_senses", lambda t: (
            contains_all(final_answer(t), ["animal", "person", "follow"]),
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
        "the Cambridge Dictionary entry page for dog")
    return ok, ev, True


if __name__ == "__main__":
    main()
