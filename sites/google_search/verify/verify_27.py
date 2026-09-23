#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--27.

Check the current air quality index in Paris.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Paris air-quality pages agree: the current air quality
    index is 78 (US AQI), category Moderate, main pollutant PM2.5 (IQAir
    Paris page and the aqicn.org Paris page both show 78 / Moderate /
    PM2.5).
Source pages: www.iqair.com/world-air-quality-ranking/paris and aqicn.org/city/paris

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Paris air-quality search | a Paris AQI page opened | answer: the
  AQI value, its category and the main pollutant
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
    j = Judge('Google Search--27', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["paris", "air"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-027-", "world-air-quality-ranking/paris", "city/paris", "paris-france"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_aqi_value", number_claim(fa, 78),
            f"final={fa[:200]!r}")
    j.check("answer_category", contains_any(fa, ["moderate"]),
            f"final={fa[:200]!r}")
    j.check("answer_main_pollutant", re_any(fa, [r"pm\s*2\.5"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
