#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--41.

Shop section: find and browse it, listing 3 items sold there.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /shop
  shop-page DOM shows the item names
  answer lists at least 3 of the shop items by name
  LLM anchored answer match + shop screenshot
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

TASK_ID = "Cambridge Dictionary--41"

NAV = "/shop"
ITEMS = ["cambridge advanced learners dictionary",
         "cambridge dictionary of american english",
         "cambridge english pronouncing dictionary",
         "cambridge grammar of english",
         "cambridge learners dictionary",
         "cambridge phrasal verbs dictionary",
         "cambridge business english dictionary",
         "cambridge thesaurus"]
GT = ("Items sold in the Cambridge Dictionary Shop include: Cambridge Advanced Learner's "
      "Dictionary (4th Edition, GBP 35.00), Cambridge Dictionary of American English "
      "(2nd Edition, GBP 29.99), Cambridge English Pronouncing Dictionary (18th Edition, "
      "GBP 39.00), Cambridge Grammar of English (GBP 55.00), Cambridge Learner's "
      "Dictionary (4th Edition, GBP 25.00), Cambridge Phrasal Verbs Dictionary "
      "(2nd Edition, GBP 22.99), Cambridge Business English Dictionary (GBP 32.50), "
      "Cambridge Thesaurus (GBP 28.00). ACCEPTANCE RULE: the task asks the agent to "
      "list three items; naming any three of these eight real shop items (with or "
      "without prices/ISBNs) fully answers the question.")
QUESTION = ("Which three (or more) items did the agent find for sale in the Cambridge "
            "Dictionary Shop section?")
SHOT_MUST = "the Cambridge Dictionary Shop page listing its items"

def main():
    run_verifier(TASK_ID, [
        ("nav_shop", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_items", lambda t: (
            count_list_matches(" ".join(observed_texts(t)), ITEMS) >= 3,
            f"page item matches={count_list_matches(' '.join(observed_texts(t)), ITEMS)}")),
        ("answer_lists_three_items", lambda t: (
            count_list_matches(final_answer(t), ITEMS) >= 3,
            f"answer item matches={count_list_matches(final_answer(t), ITEMS)}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            observed_text_at(t, NAV)), True)),
        ("screenshot_shows_shop", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "the Cambridge Dictionary Shop page")
    return ok, ev, True


if __name__ == "__main__":
    main()
