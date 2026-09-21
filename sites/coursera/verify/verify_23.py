#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--23.

Find a course about 'Artificial Intelligence Ethics' with a duration of less than 5 weeks rated 4.5 stars or higher; provide the course name and the instructor's name.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Ethics of Artificial Intelligence (Princeton, 4.8, Sandra Wachter); AI, Empathy & Ethics (Stanford, 4.7, Kathi Fisler); Everyday Ethics in Artificial Intelligence (IBM, 4.6, Seth Dobrin).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + instructor
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
    j, t, fa = load_task(a, "Coursera--23")
    opts = [
        {"slug": "ethics-of-artificial-intelligence",
        "page_tokens": ['Ethics of Artificial Intelligence'],
        "answer_tokens": ['Ethics of Artificial Intelligence', 'Sandra Wachter'],},
        {"slug": "ai-empathy-ethics",
        "page_tokens": ['AI, Empathy & Ethics'],
        "answer_tokens": ['AI, Empathy', 'Kathi Fisler'],},
        {"slug": "everyday-ethics-ai",
        "page_tokens": ['Everyday Ethics in Artificial Intelligence'],
        "answer_tokens": ['Everyday Ethics', 'Seth Dobrin'],},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
