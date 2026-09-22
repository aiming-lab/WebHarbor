#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--25.

Get the latest news headline about the English Premier League football club Manchester United.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's ManUtd.com news page leads with the match report 'United
    secure crucial three points at Old Trafford' (2 hours ago). The goal.com
    United page's latest items: 'Goal exclusive: Manchester United identify
    summer midfield target' (2h ago) and 'Garnacho late strike sees United
    past Bournemouth' (match report). Any of these is the latest United
    headline on the mirror (see the audit note on multiple headline pages).
Source pages: www.manutd.com/en/news and www.goal.com Manchester United pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Manchester United news search | a United news page opened | answer:
  the latest headline the opened page shows
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
    j = Judge('Google Search--25', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["manchester", "united"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-025-", "manutd.com/en/news", "manchester-united"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_names_united", contains_any(fa, ["united"]),
            f"final={fa[:200]!r}")
    j.check("answer_latest_headline", re_any(fa, [r"united secure", r"crucial three points", r"three points at old trafford", r"garnacho", r"summer midfield target", r"past bournemouth"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
