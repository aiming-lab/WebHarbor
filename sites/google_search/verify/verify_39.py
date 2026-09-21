#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--39.

Identify the top-10 trending travel destination for 2024 through a blog, how many of them are in Asian.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    AUDIT NOTE (see REPORT.md): the mirror's travel-blog pages describe the
    2024 trending-destinations list without naming a full top 10 — the T+L
    blog details four entries (led by 'An emerging Asian capital'), and the
    Forbes/BBC/NYT coverage notes Asia features prominently with
    cultural-heritage routes through Japan, Vietnam and Indonesia. Grading
    anchors on the blog-based Asia answer: an Asia statement plus at least
    one named Asian destination.
Source pages: www.travelandleisure.com/trip-ideas/best-places-to-go and cntraveler / Forbes / BBC travel pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a 2024 travel-destinations search | a travel blog/list page opened |
  answer: the Asian destinations of the 2024 list and how many are in Asia
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
    j = Judge('Google Search--39', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["travel", "destinations"]) or searched_all_tokens(t, ["destinations", "2024"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-039-", "this-year", "best-in-travel", "best-places-to-go", "places-to-go", "best-of-the-world", "best-travel-destinations", "best-destinations", "where-to-travel"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_addresses_asia", re_any(fa, [r"\basia\b|\basian\b"]),
            f"final={fa[:200]!r}")
    asian = ["Japan", "Vietnam", "Indonesia", "Asian capital", "Tokyo", "Seoul", "Bali", "Bangkok", "Hanoi"]
    j.check("answer_names_asian_destinations", count_names(fa, asian) >= 1,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
