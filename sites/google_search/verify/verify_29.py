#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--29.

Find out the current world record for the men's 100m sprint.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's World Athletics records page lists the men's 100m world
    record as 9.58, set in 2009 in Berlin (the progression table shows
    'Athlete A (JAM)', Aug 16, 2009; the athlete's name is anonymized on the
    mirror — see the audit note in REPORT.md).
Source pages: worldathletics.org/records/by-category/world-records

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a 100m record search | a world-records page opened | answer: the
  record time and the year/venue
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
    j = Judge('Google Search--29', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["100m"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-029-", "world-records", "100_metres_world_record_progression"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_record_time", number_claim(fa, 9.58),
            f"final={fa[:200]!r}")
    j.check("answer_year_or_venue", contains_any(fa, ["2009", "berlin"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
