#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--34.

Find 'Essentials of Global Health'; determine the instructor, summarize his bio, and note whether he offers any additional courses on Coursera.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Instructor: Richard Skolnik (Lecturer in Global Affairs, Yale University); his instructor page lists exactly 1 course on Coursera - Essentials of Global Health - so he offers no additional courses.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course + instructor page navigation | page shows '1 course on Coursera' | answer names instructor + Yale + states no additional courses
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
    j, t, fa = load_task(a, "Coursera--34")
    j.check("nav_course", navigated_to_course(t, "essentials-of-global-health"),
            "trajectory must open the Essentials of Global Health page")
    j.check("nav_instructor", navigated_to(t, "/instructor/richard-skolnik"),
            "trajectory must open the instructor page")
    page = page_text_at(t, "/learn/essentials-of-global-health")
    inst = page_text_at(t, "/instructor/richard-skolnik")
    j.check("page_shows_instructor", contains_all(page, ["Essentials of Global Health", "Richard Skolnik"]),
            "course page DOM must show the instructor")
    j.check("page_shows_single_course",
            contains_all(inst, ["Richard Skolnik", "course on Coursera",
                                "Essentials of Global Health"]),
            "instructor page DOM must show his Coursera course list")
    j.check("answer_instructor", contains_all(fa, ["Richard Skolnik", "Yale"]),
            f"final={fa[:160]!r}")
    j.check("answer_no_other_courses", states_no_other_courses(fa),
            "answer must state that he offers no additional courses")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
