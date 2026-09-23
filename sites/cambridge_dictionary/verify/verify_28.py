#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--28.

Thesaurus synonyms for 'feel giddy' (entry/article page, full list).

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav a thesaurus page whose path contains feel-giddy
  page DOM shows the synonym list
  answer lists at least 7 of the 11 synonyms shown on that page
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

TASK_ID = "Cambridge Dictionary--28"

NAV = "feel-giddy"
SEARCH_MARKS = ["feel+giddy", "feel%20giddy"]
SYNONYMS = ["feel dizzy", "feel lightheaded", "feel faint", "feel woozy",
            "feel unsteady", "feel vertiginous", "be overcome with excitement",
            "feel exhilarated", "feel euphoric", "feel elated", "be ecstatic"]
GT = ("The Cambridge Thesaurus provides these synonyms for 'feel giddy': feel dizzy, "
      "feel lightheaded, feel faint, feel woozy, feel unsteady, feel vertiginous, "
      "be overcome with excitement, feel exhilarated, feel euphoric, feel elated, "
      "be ecstatic. ACCEPTANCE RULE: the full list is shown on the entry/article "
      "page, while the thesaurus SEARCH-RESULTS page previews only the first five "
      "(feel dizzy, feel lightheaded, feel faint, feel woozy, feel unsteady). An "
      "agent that used the search-results page and reported those five previewed "
      "synonyms has completely answered the question; an agent that used the "
      "entry page should report most of the full list.")
QUESTION = ("Which synonyms does the Cambridge Dictionary thesaurus provide for "
            "'feel giddy', as shown on the page the agent used?")
SHOT_MUST = "a thesaurus page for 'feel giddy' (entry/article or search results) listing synonyms"

def _results_page(t):
    return any(any(m in u for m in SEARCH_MARKS) and "/thesaurus" in u
               for u in step_urls(t) if is_mirror_url(u))

def _nav_ok(t):
    # entry/article page, or the thesaurus search results for the phrase
    return navigated_to(t, NAV) or _results_page(t)

def _lists_synonyms(t):
    c = count_list_matches(final_answer(t), SYNONYMS)
    if navigated_to(t, NAV):
        return c >= 7      # entry/article page: report the (near-)full list
    return c >= 5          # search-results page: report everything it previews

def main():
    run_verifier(TASK_ID, [
        ("nav_thesaurus", lambda t: (
            _nav_ok(t), f"entry={navigated_to(t, NAV)} results={_results_page(t)}")),
        ("page_shows_synonyms", lambda t: (
            count_list_matches(" ".join(observed_texts(t)), SYNONYMS) >= 4,
            f"page synonym matches={count_list_matches(' '.join(observed_texts(t)), SYNONYMS)}")),
        ("answer_lists_synonyms", lambda t: (
            _lists_synonyms(t),
            f"answer synonym matches={count_list_matches(final_answer(t), SYNONYMS)}")),
        ("answer_matches_ground_truth", lambda t: (
            *llm_text_match(final_answer(t), GT, QUESTION,
                            " ".join(observed_texts(t))), True)),
        ("screenshot_shows_thesaurus", lambda t: _shot_check(t)),
    ])


def _shot_check(t):
    s = shot_after_url(t, NAV) or last_shot(t)
    if not s:
        return False, "no screenshots in run", True
    ok, ev = llm_screenshot_shows(s, SHOT_MUST,
        "a Cambridge thesaurus page for 'feel giddy'")
    return ok, ev, True


if __name__ == "__main__":
    main()
