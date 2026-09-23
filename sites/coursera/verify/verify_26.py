#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--26.

Identify a beginner-level Specialization offering an overview of 'Renewable Energy' that includes a course on Renewable Energy Futures; note the instructor's name and the weeks needed at 5 hours a week.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Renewable Energy and Green Building Entrepreneurship Specialization' (Duke University, Bruce Usher) includes the course 'Renewable Energy Futures' (Approx. 15 hours) -> 15h / 5h-per-week = 3 weeks for that course; the whole Specialization is 4 Months (~12 weeks at 5h/week). Both readings accepted.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows the Renewable Energy Futures course | answer names Bruce Usher + a week count (3 or 12)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (parse_args, load_task, check_read_only, grade_options,
                        course_option_ok, search_card_ok,
                        navigated_to, navigated_any, navigated_to_course, query_has, page_text_at,
                        contains_all, contains_any, counts, has_number, numbers_in,
                        pct_of, star_level_lowest, re_found, fold, is_mirror_url,
                        states_no_other_courses,
                        step_urls, _url_path)


def main():
    a = parse_args()
    j, t, fa = load_task(a, "Coursera--26")
    page = page_text_at(t, "/learn/renewable-energy-green-building-specialization")
    j.check("nav_specialization",
            navigated_to_course(t, "renewable-energy-green-building-specialization"),
            "trajectory must open the Renewable Energy Specialization page")
    j.check("page_shows_specialization", contains_all(page, ["Renewable Energy and Green Building"]),
            "observed DOM must show the Specialization page")
    j.check("answer_instructor", contains_all(fa, ["Bruce Usher"]), f"final={fa[:160]!r}")
    j.check("answer_weeks", counts(fa, 3, "week", "weeks") or counts(fa, 12, "week", "weeks"),
            "answer must state the weeks required at 5 hours a week (3 for the Renewable Energy "
            "Futures course / 12 for the whole Specialization)")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
