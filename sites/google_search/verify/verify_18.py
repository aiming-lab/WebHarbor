#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--18.

When and where the most recent World Cup was held, and which team was the winner?

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's FIFA recent-tournaments page lists 2022 Qatar with the final
    Argentina vs France 3-3 (4-2 pens): the most recent World Cup was held in
    Qatar in 2022 and Argentina won. Russia 2018 (France) and Brazil 2014
    (Germany) are the older rows.
Source pages: www.fifa.com/tournaments/mens/worldcup/recent

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a World Cup search | a World Cup page opened | answer: the host, year
  and winner of the most recent World Cup
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
    j = Judge('Google Search--18', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["world", "cup"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-018-", "worldcup/recent", "worldcup", "world-cup"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_host_country", contains_any(fa, ["qatar"]),
            f"final={fa[:200]!r}")
    j.check("answer_year", re_any(fa, [r"\b2022\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_winner", contains_any(fa, ["argentina"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
