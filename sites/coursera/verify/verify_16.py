#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--16.

For 'Introduction to Finance: The Basics': the course instructor and the other courses he teaches.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Instructor: Gautam Kaul (Professor of Finance, University of Michigan); his instructor page lists 2 courses: Introduction to Finance: The Basics and Finance for Non-Finance Professionals.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course + instructor page navigation | page shows both courses | answer names instructor + other course
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
    j, t, fa = load_task(a, "Coursera--16")
    j.check("nav_course", navigated_to_course(t, "introduction-to-finance-the-basics"),
            "trajectory must open the course page")
    j.check("nav_instructor", navigated_to(t, "/instructor/gautam-kaul"),
            "trajectory must open the instructor page")
    page = page_text_at(t, "/learn/introduction-to-finance-the-basics")
    inst = page_text_at(t, "/instructor/gautam-kaul")
    j.check("page_shows_instructor", contains_all(page, ["Introduction to Finance: The Basics", "Gautam Kaul"]),
            "course page DOM must show the instructor")
    j.check("page_shows_other_courses", contains_all(inst, ["Finance for Non-Finance Professionals"]),
            "instructor page DOM must show the other course")
    j.check("answer_instructor", contains_all(fa, ["Gautam Kaul"]),
            f"final={fa[:160]!r}")
    j.check("answer_other_courses", contains_all(fa, ["Finance for Non-Finance Professionals"]),
            "answer must name the other course he teaches")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
