#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--5.

Identify a Specialization that teaches C++ programming for beginners; provide the name and the learning outcomes.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Coding for Everyone: C and C++ Specialization' (UC San Diego; outcomes: Write C programs, Use C++ classes and objects, Implement data structures, Build real-world applications) and 'C++ Programming for Beginners Specialization' (Duke; outcomes: Write a complete C++ program, Use classes and objects, Manage memory).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows the specialization | answer names it + >=2 learning outcomes
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
    j, t, fa = load_task(a, "Coursera--5")
    out_cc = ["Write C programs", "Use C++ classes and objects", "Implement data structures",
              "Build real-world applications"]
    out_duke = ["Write a complete C++ program", "Use classes and objects", "Manage memory"]
    n_cc = sum(1 for o in out_cc if contains_all(fa, [o]))
    n_duke = sum(1 for o in out_duke if contains_all(fa, [o]))
    opts = [
        {"slug": "coding-everyone-c-cpp",
        "page_tokens": ['Coding for Everyone: C and C++ Specialization', 'Write C programs'],
        "answer_tokens": ['Coding for Everyone'],
        "extra": [("answer_learning_outcomes", n_cc >= 2, f"outcomes matched={n_cc}/4 of {out_cc}")]},
        {"slug": "cpp-programming-beginners-specialization",
        "page_tokens": ['C++ Programming for Beginners Specialization'],
        "answer_tokens": ['C++ Programming for Beginners'],
        "extra": [("answer_learning_outcomes", n_duke >= 2, f"outcomes matched={n_duke}/3 of {out_duke}")]},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
