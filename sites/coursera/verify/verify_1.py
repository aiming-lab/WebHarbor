#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--1.

Search for a beginner-level online course about Python programming, suitable for someone with no programming experience.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Python for Everybody' and 'Programming for Everybody (Getting Started with Python)' (University of Michigan, Charles Severance) both explicitly require no prior experience.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names the course
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
    j, t, fa = load_task(a, "Coursera--1")
    opts = [
        {"slug": "python-for-everybody",
        "page_tokens": ['Python for Everybody'],
        "answer_tokens": ['Python for Everybody'],},
        {"slug": "programming-for-everybody",
        "page_tokens": ['Programming for Everybody'],
        "answer_tokens": ['Programming for Everybody'],},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
