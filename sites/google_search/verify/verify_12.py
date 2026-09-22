#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--12.

Find the year that Tom Brady had the most touchdowns in a single seasson.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's NFL.com Brady records page and the Pro-Football-Reference
    page agree: Tom Brady's single-season passing-TD peak is 50 touchdown
    passes in the 2007 season with the New England Patriots (2007: 16 games,
    398/578, 4,806 yds, 50 TD).
Source pages: www.nfl.com/news/tom-brady-records and www.pro-football-reference.com BradTo00

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Brady search | a Brady records/stats page opened | answer: the year
  and the touchdown total of his best season
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
    j = Judge('Google Search--12', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["brady"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-012-", "tom-brady-records", "BradTo00", "players/tom-brady"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_record_year", re_any(fa, [r"\b2007\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_touchdown_total", number_claim(fa, 50, unit_words=("touchdown", "td", "passing")),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
