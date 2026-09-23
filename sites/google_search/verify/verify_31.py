#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--31.

Discover which year Cristiano Ronaldo scored the most goals in a single season.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    AUDIT NOTE (see REPORT.md): no mirror page states Ronaldo's most-goals
    season; the mirror corroborates only that he 'has set numerous
    single-season and career scoring records'. The accepted answer is the
    widely documented peak: the 2013-14/2014-15 era with 50+ goals (his
    Real Madrid peak: 61 goals in 2014-15 all competitions; 51 in La Liga in
    2013-14). Grading anchors on a season year in 2011-2015 with a 50-69
    goal total.
Source pages: the Ronaldo career pages on the mirror (ESPN, FIFA, UEFA, Transfermarkt)

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Ronaldo search | a Ronaldo page opened | answer: a specific season
  year and goal total for his most prolific season
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
    j = Judge('Google Search--31', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["ronaldo"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-031-", "cristiano-ronaldo"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_names_ronaldo", contains_any(fa, ["ronaldo"]),
            f"final={fa[:200]!r}")
    j.check("answer_season_year", re_any(fa, [r"\b201[1-5]\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_goal_total", re_any(fa, [r"\b(5[0-9]|6[0-9])\b"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
