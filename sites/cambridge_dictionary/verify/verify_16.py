#!/usr/bin/env python3
"""Deterministic verifier for Cambridge Dictionary task Cambridge Dictionary--16.

Definition, pronunciation, and two example sentences in different contexts for cryptocurrency.

Checks (deterministic first; LLM utilities anchored on ground truth):
  nav /dictionary/english/cryptocurrency
  entry DOM shows headword + IPA
  answer contains the IPA notation and the definition as shown
  answer provides two distinct example sentences using the word
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

TASK_ID = "Cambridge Dictionary--16"

NAV = "/dictionary/english/cryptocurrency"
HEADWORD = "cryptocurrency"
IPA_UK = r"""ˈkrɪptəʊˌkɜːrənsi"""
IPA_US = r"""ˈkrɪptoʊˌkɜːrənsi"""
DEF_ANY = ["digital currency produced by a public network",
           "uses cryptography to make sure payments"]
GT = ("cryptocurrency, noun [C, U], level C1. UK IPA /ˈkrɪptəʊˌkɜːrənsi/, US IPA /ˈkrɪptoʊˌkɜːrənsi/. "
      "Definition: A digital currency produced by a public network, rather than any government, "
      "that uses cryptography to make sure payments are sent and received safely. "
      "The task asks to use the word in two example sentences illustrating different contexts: "
      "quoting two of the on-page examples (Bitcoin is the best-known cryptocurrency. / "
      "Many investors have lost money in volatile cryptocurrency markets. / "
      "Cryptocurrency transactions are recorded on a blockchain.) OR writing two new "
      "grammatical sentences that correctly use the word in two different contexts BOTH "
      "fully answer the question.")
QUESTION = ("What are the definition and pronunciation of cryptocurrency as shown in the "
            "Cambridge Dictionary, and two example sentences using the word in different contexts?")
SHOT_MUST = "the dictionary entry for cryptocurrency with its IPA pronunciation"

def main():
    run_verifier(TASK_ID, [
        ("nav_entry", lambda t: (navigated_to(t, NAV), f"nav={navigated_to(t, NAV)}")),
        ("page_shows_entry", lambda t: (
            fold(HEADWORD) in fold(observed_text_at(t, NAV))
            and ipa_contains(observed_text_at(t, NAV), IPA_UK),
            "entry DOM must show the headword and its IPA")),
        ("answer_pronunciation", lambda t: (
            ipa_contains(final_answer(t), IPA_UK) or ipa_contains(final_answer(t), IPA_US),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_definition", lambda t: (
            contains_any(final_answer(t), DEF_ANY),
            f"final={final_answer(t)[:150]!r}")),
        ("answer_two_example_sentences", lambda t: (
            count_word_sentences(final_answer(t), "cryptocurrency", 2) >= 2,
            f"distinct word sentences={count_word_sentences(final_answer(t), 'cryptocurrency', 2)}")),
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
        "the Cambridge Dictionary entry page for cryptocurrency")
    return ok, ev, True


if __name__ == "__main__":
    main()
