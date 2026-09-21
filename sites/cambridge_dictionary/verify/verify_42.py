#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--42.

Convert the Cambridge Dictionary homepage from English (UK) to Deutsch.

Checks (deterministic first; LLM utilities anchored on ground truth):
  the run ends on the homepage path / (the language switch redirects back to the homepage; the switch action + German-DOM + vision checks carry the proof)
  a language-switch action selecting Deutsch (select/input with text Deutsch)
  homepage DOM afterwards shows the German UI strings
  answer confirms the conversion to Deutsch/German
  LLM anchored answer match + German homepage screenshot
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

TASK_ID = "Cambridge Dictionary--42"

from verify_lib import final_url, final_url_is_path

NAV = "/"
TARGET_LANG = "Deutsch"
GERMAN_MARKS = ["wörterbuch", "finden sie das perfekte wort"]
GT = ("The homepage UI language was switched from English (UK) to Deutsch: the site name "
      "shows 'Cambridge Wörterbuch', the hero shows 'Finden Sie das perfekte Wort', and the "
      "search placeholder shows 'Im Cambridge Wörterbuch suchen'.")
QUESTION = "Was the Cambridge Dictionary homepage converted from English (UK) to Deutsch?"
SHOT_MUST = ("the Cambridge homepage in German: 'Cambridge Wörterbuch' and the hero "
             "'Finden Sie das perfekte Wort'")

def _switch_action(t):
    for s in t.get("steps") or []:
        params = s.get("params") or {}
        text = str(params.get("text") or params.get("keys") or "")
        if fold(text) == fold(TARGET_LANG):
            return True
    return False

def _german_dom(t):
    dom = fold(" ".join(observed_texts(t)))
    return any(m in dom for m in GERMAN_MARKS)

def main():
    run_verifier(TASK_ID, [
        ("nav_ends_on_homepage", lambda t: (
            final_url_is_path(t, "/"), f"final_url={final_url(t)}")),
        ("switch_action_selects_deutsch", lambda t: (
            _switch_action(t), "an action param must select Deutsch")),
        ("page_shows_german_ui", lambda t: (
            _german_dom(t), "homepage DOM must show German UI strings")),
        ("answer_confirms_german", lambda t: (
            contains_any(fold(final_answer(t)),
                         ["wörterbuch", "deutsch", "german", "finden sie"]),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            " ".join(observed_texts(t))), True)),
        ("screenshot_shows_german_home", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Cambridge Dictionary homepage after switching to Deutsch")
    return ok, ev, True


if __name__ == "__main__":
    main()
