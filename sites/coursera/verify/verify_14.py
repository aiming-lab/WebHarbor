#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--14.

Find a course related to Introductory Project Management that includes modules on Agile methodology.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Introduction to Project Management' (University of Melbourne) includes the module 'Agile Project Management' (Scrum, sprints, and agile practices).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the Agile module | answer names course + Agile
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
    j, t, fa = load_task(a, "Coursera--14")
    opts = [
        {"slug": "introduction-to-project-management",
        "page_tokens": ['Introduction to Project Management', 'Agile Project Management'],
        "answer_tokens": ['Introduction to Project Management', 'Agile'],},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
