#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--21.

Spanish translation of ephemeral as shown by the dictionary (entry page or Translate).

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav the ephemeral entry page or a Translate URL carrying the word
  page DOM shows the source page content
  answer gives the Spanish translation as shown
  LLM anchored answer match + screenshot
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

TASK_ID = "Cambridge Dictionary--21"

ENTRY_NAV = "/dictionary/english/ephemeral"
TRANSLATE_NAV = "/translate"
WORD = "ephemeral"
SPANISH = "efímero"
GT = "The Spanish translation of ephemeral given by the Cambridge Dictionary is efímero."
QUESTION = "What is the Spanish translation of the word ephemeral in the Cambridge Dictionary?"
ENTRY_SHOT = "the dictionary entry for ephemeral with its IPA pronunciation"
TRANSLATE_SHOT = "the Translate page showing a Spanish translation result for ephemeral"

def _nav_ok(t):
    if navigated_to(t, ENTRY_NAV):
        return True
    return any(WORD in u.casefold() for u in nav_urls(t, TRANSLATE_NAV))

def _page_ok(t):
    if navigated_to(t, ENTRY_NAV):
        return fold(WORD) in fold(observed_text_at(t, ENTRY_NAV))
    for u in nav_urls(t, TRANSLATE_NAV):
        if WORD in u.casefold():
            dom = observed_text_at(t, TRANSLATE_NAV)
            if dom and SPANISH in dom:
                return True
    return False

def main():
    run_verifier(TASK_ID, [
        ("nav_word_or_translate", lambda t: (
            _nav_ok(t), f"entry={navigated_to(t, ENTRY_NAV)} "
                        f"translate_with_word={any(WORD in u.casefold() for u in nav_urls(t, TRANSLATE_NAV))}")),
        ("page_shows_source", lambda t: (_page_ok(t), "source page DOM must show the content")),
        ("answer_spanish_translation", lambda t: (
            contains_translation(final_answer(t), [SPANISH]),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, ENTRY_NAV)
                            or observed_text_at(t, TRANSLATE_NAV)), True)),
        ("screenshot_shows_source", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, ENTRY_NAV)
    if s:
        ok, ev = llm_screenshot_shows(s, ENTRY_SHOT,
            "the Cambridge Dictionary entry page for ephemeral")
        return ok, ev, True
    s = last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, TRANSLATE_SHOT,
        "the Cambridge Dictionary Translate page for ephemeral")
    return ok, ev, True


if __name__ == "__main__":
    main()
