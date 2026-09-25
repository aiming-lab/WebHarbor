#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--12.

Look for a Coursera course (not Specialization) that teaches Java programming basics.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Java courses (Course type): Object Oriented Programming in Java (UC San Diego); Java Programming Basics (UC San Diego); Java Programming and Software Engineering Fundamentals (Duke).

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
    j, t, fa = load_task(a, "Coursera--12")
    opts = [
        {"slug": "object-oriented-programming-java",
        "page_tokens": ['Object Oriented Programming in Java'],
        "answer_tokens": ['Object Oriented Programming in Java'],
        "card_tokens": ['Object Oriented Programming in Java', 'University of California, San Diego'],},
        {"slug": "java-programming-basics",
        "page_tokens": ['Java Programming Basics'],
        "answer_tokens": ['Java Programming Basics'],
        "card_tokens": ['Java Programming Basics', 'University of California, San Diego'],},
        {"slug": "java-programming-software-engineering",
        "page_tokens": ['Java Programming and Software Engineering'],
        "answer_tokens": ['Java Programming and Software Engineering'],
        "card_tokens": ['Java Programming and Software Engineering Fundamentals', 'Duke University'],},
    ]
    via_detail = any(course_option_ok(t, fa, o) for o in opts)
    via_card = search_card_ok(t, fa, opts)
    if via_detail or via_card:
        j.evidence.append('[PASS] evidence_on_mirror: ' +
                          ('course detail page' if via_detail else 'search results card'))
    else:
        grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
