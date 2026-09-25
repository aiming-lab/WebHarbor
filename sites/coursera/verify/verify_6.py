#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--6.

Identify the course 'Artificial Intelligence for Healthcare' and note the course duration and the number of quizzes in Assessments.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Artificial Intelligence for Healthcare' (Stanford) lasts Approx. 20 hours; its four modules carry 1+2+1+1 = 5 quizzes in total.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows course + module quiz stats | answer gives 20 hours + 5 quizzes
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
    j, t, fa = load_task(a, "Coursera--6")
    page = page_text_at(t, "/learn/artificial-intelligence-healthcare")
    j.check("nav_course", navigated_to_course(t, "artificial-intelligence-healthcare"),
            "trajectory must open the Artificial Intelligence for Healthcare page")
    j.check("page_shows_course", contains_all(page, ["Artificial Intelligence for Healthcare", "quizzes"]),
            "observed DOM must show the course and its module quiz counts")
    j.check("answer_names_course", contains_all(fa, ["Artificial Intelligence for Healthcare"]),
            f"final={fa[:160]!r}")
    j.check("answer_duration_hours", counts(fa, 20, "hour", "hours"),
            "answer must state the Approx. 20 hours duration")
    j.check("answer_quiz_count", counts(fa, 5, "quiz", "quizzes"),
            "answer must state 5 quizzes in total")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
