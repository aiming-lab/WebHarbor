#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--25.

Two different meanings of harmony as given in the dictionary entry.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/harmony
  entry DOM shows headword + IPA
  answer covers sense 1 (people/things agreeing) and sense 2 (music)
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

TASK_ID = "Cambridge Dictionary--25"

NAV = "/dictionary/english/harmony"
HEADWORD = "harmony"
IPA_UK = r"""/ˈhɑːməni/"""
SENSE1_ANY = ["peaceful and agree with each other", "things seem right or suitable together"]
SENSE2_ANY = ["combination of musical notes", "pleasing effect"]
GT = ("harmony, noun, level B2. UK IPA /ˈhɑːməni/, US IPA /ˈhɑːrməni/. Two meanings: "
      "1. A situation in which people are peaceful and agree with each other, or when "
      "things seem right or suitable together. "
      "2. The combination of musical notes played or sung at the same time to give a "
      "pleasing effect.")
QUESTION = "What two different meanings of harmony does the Cambridge Dictionary give?"
SHOT_MUST = "the dictionary entry for harmony with its IPA pronunciation"

def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_entry", lambda t: (
            fold(HEADWORD) in fold(observed_text_at(t, NAV))
            and ipa_contains(observed_text_at(t, NAV), IPA_UK),
            "entry DOM must show the headword and its IPA")),
        ("answer_sense_people", lambda t: (
            contains_any(final_answer(t), SENSE1_ANY), f"final={final_answer(t)[:150]!r}")),
        ("answer_sense_music", lambda t: (
            contains_any(final_answer(t), SENSE2_ANY), f"final={final_answer(t)[:150]!r}")),
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
        "the Cambridge Dictionary entry page for harmony")
    return ok, ev, True


if __name__ == "__main__":
    main()
