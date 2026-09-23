#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--8.

Find a free course related to 'R for Data Science' (Free tag) and report the language the course is taught in.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): The free R courses (R Programming; R for Data Science and Machine Learning; Data Science: R Basics; Statistics with R Specialization) all state 'English . Subtitles available'.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer states English
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
    j, t, fa = load_task(a, "Coursera--8")
    opts = [
        {"slug": "r-programming",
        "page_tokens": ['R Programming'],
        "answer_tokens": ['English'],},
        {"slug": "r-data-science-machine-learning",
        "page_tokens": ['R for Data Science and Machine Learning'],
        "answer_tokens": ['English'],},
        {"slug": "data-science-r-basics",
        "page_tokens": ['Data Science: R Basics'],
        "answer_tokens": ['English'],},
        {"slug": "statistics-r-specialization",
        "page_tokens": ['Statistics with R Specialization'],
        "answer_tokens": ['English'],},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
