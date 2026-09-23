#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--11.

According to FlightAware, tell me the busiest airport last week and its total arrivals and departures last week.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's FlightAware dashboard lists 'Busiest airports this week':
    1. Hartsfield-Jackson Atlanta (ATL) with 5,820 arrivals, 5,830 departures
    and 11,650 total operations; 2. Dallas/Fort Worth 10,860; 3. Denver
    10,300; 4. Chicago O'Hare 9,810; 5. Los Angeles 8,510.
Source pages: www.flightaware.com/live/airport_status_bigmap.rvt and flightaware.com/live/airport

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a busiest-airport search | a FlightAware page opened | answer: the
  busiest airport and its weekly total operations
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
    j = Judge('Google Search--11', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["busiest", "airport"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-011-", "airport_status_bigmap", "flightaware.com/live/airport", "airport-technology", "centreforaviation"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_busiest_airport", contains_any(fa, ["atlanta", "hartsfield"]),
            f"final={fa[:200]!r}")
    j.check("answer_total_operations", number_claim(fa, 11650),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
