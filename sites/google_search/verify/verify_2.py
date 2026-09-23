#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--2.

Search for the latest news title about the NBA team the Los Angeles Lakers.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Lakers.com news page leads with 'Lakers hold off Wolves in
    fourth-quarter rally at Crypto.com Arena' (post-game news, 124-110 over
    the Wolves). The SERP also carries the news card 'Lakers top Nuggets
    112-105' (LeBron James 31 points). Either headline is the latest Lakers
    news title the mirror provides.
Source pages: www.lakers.com/news and the ESPN Lakers-latest-score news card on the SERP

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Lakers news search | answer: a latest-news headline the mirror shows
  (Wolves rally headline or the Nuggets news card)
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
    j = Judge('Google Search--2', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["lakers"]),
            "a /search?q= step carrying the task's key tokens")
    wolves = contains_any(fa, ["wolves"]) and re_any(fa, [r"fourth[- ]quarter rally", r"124\s*[-\u2013]\s*110"])
    nuggets = contains_any(fa, ["nuggets"]) and re_any(fa, [r"112\s*[-\u2013]\s*105"])
    j.check("answer_lakers_headline", (wolves or nuggets),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
