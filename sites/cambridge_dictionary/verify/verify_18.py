#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--18.

Thesaurus synonyms for 'to behave well' (article/entry page, full list).

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav a thesaurus page whose path contains to-behave-well
  page DOM shows the synonym list
  answer lists at least 6 of the 10 synonyms shown on that page
  LLM anchored answer match + thesaurus screenshot
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

TASK_ID = "Cambridge Dictionary--18"

NAV = "to-behave-well"
SYNONYMS = ["behave yourself", "behave", "be on your best behaviour",
            "conduct yourself", "mind your manners", "be well-behaved",
            "act appropriately", "toe the line", "play by the rules",
            "show good conduct"]
GT = ("Synonyms for 'to behave well' shown in the Cambridge Thesaurus article: "
      "behave yourself, behave, be on your best behaviour, conduct yourself, "
      "mind your manners, be well-behaved, act appropriately, toe the line, "
      "play by the rules, show good conduct.")
QUESTION = "Which synonyms does the Cambridge Dictionary thesaurus give for 'to behave well'?"
SHOT_MUST = "the thesaurus article for 'to behave well' listing its synonyms"

def main():
    run_verifier(TASK_ID, [
        ("nav_thesaurus_article", lambda t: (
            navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_synonyms", lambda t: (
            count_list_matches(" ".join(observed_texts(t)), SYNONYMS) >= 6,
            f"page synonym matches={count_list_matches(' '.join(observed_texts(t)), SYNONYMS)}")),
        ("answer_lists_synonyms", lambda t: (
            count_list_matches(final_answer(t), SYNONYMS) >= 6,
            f"answer synonym matches={count_list_matches(final_answer(t), SYNONYMS)}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_article", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Cambridge thesaurus article page for 'to behave well'")
    return ok, ev, True


if __name__ == "__main__":
    main()
