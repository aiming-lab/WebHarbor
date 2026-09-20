#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--41.

Look up the current statistics of air pollution level in Los Angeles using Google Search.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    AUDIT NOTE (see REPORT.md): the mirror's LA air-quality pages disagree
    on the current value — AirNow shows 105 (Unhealthy for Sensitive
    Groups), IQAir 92 (Moderate, PM2.5), BreezoMeter 71 (Moderate, PM2.5 17
    ug/m3), aqicn.org 95 (Moderate). Grading accepts any page-consistent
    (value, category) pair; the answer must match one of the mirror's
    pages.
Source pages: www.airnow.gov, www.iqair.com/usa/california/los-angeles, breezometer, aqicn.org

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an LA air-quality search | an LA air-quality page opened | answer: the
  current AQI value and its category
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
    j = Judge('Google Search--41', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["angeles", "air"]) or searched_all_tokens(t, ["angeles", "pollution"]) or searched_all_tokens(t, ["angeles", "aqi"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-041-", "airnow.gov", "usa/california/los-angeles", "los-angeles-ca", "city/losangeles"]),
            "an answer-bearing mirror page was opened")
    airnow = number_claim(fa, 105) and contains_any(fa, ["unhealthy for sensitive", "usg"])
    iqair = number_claim(fa, 92) and contains_any(fa, ["moderate"])
    breezo = number_claim(fa, 71) and contains_any(fa, ["moderate"])
    aqicn = number_claim(fa, 95) and contains_any(fa, ["moderate"])
    j.check("answer_aqi_value_and_category", (airnow or iqair or breezo or aqicn),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
