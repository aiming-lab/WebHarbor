#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--6.

Browse the monthly trending searches in Columbus.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Google Trends page for Columbus (geo=US-OH, past 30 days)
    lists the top queries: local sports team (100), weekend events (82),
    school district news (64), downtown construction (48), plus rising
    queries (marathon route map, spring break activities, new mayor
    announcement, city budget vote). The Experience Columbus page narrates
    this month's local trends: Ohio State football home schedule, downtown
    infrastructure project, restaurants / Short North gallery hop, Columbus
    Crew and Blue Jackets. Cleveland/Chicago/LA trends pages are distractors.
Source pages: trends.google.com/trends/explore?geo=US-OH&q=columbus and www.experiencecolumbus.com/whats-happening

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Columbus trending search | the Columbus trends page (or the Columbus
  events page) opened | answer: the trending searches the page lists
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
    j = Judge('Google Search--6', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["columbus", "trending"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-006-", "geo=us-oh", "experiencecolumbus"]),
            "an answer-bearing mirror page was opened")
    trends_page = (contains_all(fa, ["local sports team", "weekend events"])
                  and contains_any(fa, ["school district news", "downtown construction"]))
    experience = count_names(fa, ["Ohio State football", "Columbus Crew", "Blue Jackets",
                                 "Short North", "gallery hop"]) >= 2
    j.check("answer_columbus_trends", (trends_page or experience),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
