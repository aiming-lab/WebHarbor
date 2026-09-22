#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--19.

Try a Cambridge Dictionary translation and report which company provided it.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /translate on the mirror
  a translation was actually submitted (translate URL carries q=)
  translate-page DOM shows the provider attribution
  answer names the translation provider shown on the page
  LLM anchored answer match + translate-page screenshot
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

TASK_ID = "Cambridge Dictionary--19"

NAV = "/translate"
PROVIDER_LINE = "Translation provided by Microsoft"
GT = ("The Cambridge Dictionary translations are provided by Microsoft "
      "(the Translate page states: Translation provided by Microsoft, powered by "
      "Microsoft Translator).")
QUESTION = "Which company provided the Cambridge Dictionary translation?"
SHOT_MUST = "the Translate page showing 'Translation provided by Microsoft'"

def _tried_translation(t):
    return any("q=" in u for u in nav_urls(t, NAV))

def main():
    run_verifier(TASK_ID, [
        ("nav_translate", lambda t: (
            navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("tried_translation", lambda t: (
            _tried_translation(t),
            f"translate urls with q={sum(1 for u in nav_urls(t, NAV) if 'q=' in u)}")),
        ("page_shows_provider", lambda t: (
            PROVIDER_LINE in " ".join(observed_texts(t)),
            "translate-page DOM must show the provider attribution")),
        ("answer_names_provider", lambda t: (
            "microsoft" in fold(final_answer(t)),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_translate", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Cambridge Dictionary Translate page")
    return ok, ev, True


if __name__ == "__main__":
    main()
