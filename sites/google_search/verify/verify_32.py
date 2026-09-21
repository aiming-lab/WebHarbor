#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--32.

Find out where and when the most recent UEFA Champions League final was held, and which team won.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's UEFA finals archive lists 2024: Wembley, London — Borussia
    Dortmund vs Real Madrid 0-2: the most recent final was held at Wembley
    (London) in 2024 and Real Madrid won 2-0. (The mirror states the year;
    the exact day is not on the page — see the audit note in REPORT.md.)
Source pages: www.uefa.com/uefachampionsleague/history/finals

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Champions League final search | the UEFA finals page opened |
  answer: the venue, year, winner and score
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
    j = Judge('Google Search--32', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["champions", "league"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-032-", "history/finals", "uefachampionsleague"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_venue", contains_any(fa, ["wembley"]),
            f"final={fa[:200]!r}")
    j.check("answer_year", re_any(fa, [r"\b2024\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_winner", contains_any(fa, ["real madrid"]),
            f"final={fa[:200]!r}")
    j.check("answer_finalist_and_score", contains_any(fa, ["dortmund"]) and re_any(fa, [r"\b2\s*[-\u2013]\s*0\b", r"\b0\s*[-\u2013]\s*2\b"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
