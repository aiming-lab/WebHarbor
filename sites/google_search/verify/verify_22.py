#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--22.

Browse and list the top three trending topics this month in New York City.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Google Trends page for New York (geo=US-NY, past 30 days)
    lists the top queries: local sports team (100), weekend events (82),
    school district news (64), then downtown construction (48); rising
    queries: marathon route map, spring break activities, new mayor
    announcement, city budget vote. LA/Miami trends pages are distractors.
Source pages: trends.google.com/trends/explore?geo=US-NY on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an NYC trending search | the New York trends page opened | answer: the
  top trending topics the page lists
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
    j = Judge('Google Search--22', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["york", "trending"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-022-", "geo=us-ny"]),
            "an answer-bearing mirror page was opened")
    topics = contains_all(fa, ["local sports team", "weekend events"]) and \
        contains_any(fa, ["school district news", "downtown construction"])
    j.check("answer_nyc_trending_topics", topics,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
