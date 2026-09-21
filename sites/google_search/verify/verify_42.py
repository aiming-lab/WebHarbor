#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--42.

Use Google Search to find an article that explains the major differences between American English and British English.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's articles (Babbel, Grammarly, Oxford International English)
    explain the difference categories with concrete spelling examples —
    colour/color, flavour/flavor, centre/center, theatre/theater,
    organise/organize, defence/defense, licence/license — plus vocabulary
    differences and pronunciation (rhoticity).
Source pages: www.babbel.com/en/magazine/british-vs-american-english and the Grammarly / Oxford pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an American vs British English search | an article page opened |
  answer: the spelling difference examples plus at least one more difference category
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--42', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["english"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-042-", "british-vs-american-english", "british-english-vs-american-english", "differences-in-american-and-british-english"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_spelling_pair_color", contains_any(fa, ["color"]),
            f"final={fa[:200]!r}")
    j.check("answer_spelling_pair_colour", contains_any(fa, ["colour"]),
            f"final={fa[:200]!r}")
    pairs = ["centre", "center", "organise", "organize", "honour", "honor",
             "theatre", "theater", "defence", "defense", "licence", "license",
             "traveled", "travelled"]
    j.check("answer_more_spelling_examples", count_names(fa, pairs) >= 1,
            f"final={fa[:200]!r}")
    cats = ["pronunciation", "rhotic", "vocabulary", "lift", "elevator", "lorry",
            "truck", "boot", "trunk", "flat", "apartment", "gotten"]
    j.check("answer_another_difference_category", count_names(fa, cats) >= 1,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
