#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--19.

Identify the course that provides an introduction to Psychology; list the instructor, the institution, and the approximate hours to complete.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Introduction to Psychology' (Yale University, Paul Bloom, Approx. 14 hours).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows instructor | answer names instructor + Yale + 14 hours
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
    j, t, fa = load_task(a, "Coursera--19")
    page = page_text_at(t, "/learn/introduction-to-psychology")
    j.check("nav_course", navigated_to_course(t, "introduction-to-psychology"),
            "trajectory must open the Introduction to Psychology page")
    j.check("page_shows_course", contains_all(page, ["Introduction to Psychology", "Paul Bloom"]),
            "observed DOM must show the course and its instructor")
    j.check("answer_course_facts", contains_all(fa, ["Paul Bloom", "Yale"]),
            f"final={fa[:160]!r}")
    j.check("answer_hours", counts(fa, 14, "hour", "hours"),
            "answer must state the Approx. 14 hours duration")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
