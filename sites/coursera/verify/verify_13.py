#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--13.

Look for a Specialization that teaches Python programming and identify the skills you will learn.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Python 3 Programming Specialization (UMich; skills: Functions, Files and Dictionaries, Data Collection, Classes); Applied Data Science with Python Specialization (UMich; skills: Data Science, Machine Learning, Text Mining, Social Network Analysis); Advanced Python Programming Specialization (Rice; skills: Async, Decorators, Concurrency, Performance).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows the skills | answer names it + >=2 skills
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
    j, t, fa = load_task(a, "Coursera--13")
    sk_py3 = ["Functions", "Files and Dictionaries", "Data Collection", "Classes"]
    sk_ads = ["Data Science", "Machine Learning", "Text Mining", "Social Network Analysis"]
    sk_adv = ["Async", "Decorators", "Concurrency", "Performance"]
    n_py3 = sum(1 for s in sk_py3 if contains_all(fa, [s]))
    n_ads = sum(1 for s in sk_ads if contains_all(fa, [s]))
    n_adv = sum(1 for s in sk_adv if contains_all(fa, [s]))
    opts = [
        {"slug": "python-3-programming-specialization",
        "page_tokens": ['Python 3 Programming Specialization', 'Skills'],
        "answer_tokens": ['Python 3 Programming'],
        "card_tokens": ['Python 3 Programming Specialization', 'University of Michigan'],
        "extra": [("answer_skills", n_py3 >= 2, f"skills matched={n_py3}/4 of {sk_py3}")]},
        {"slug": "applied-data-science-python",
        "page_tokens": ['Applied Data Science with Python Specialization', 'Skills'],
        "answer_tokens": ['Applied Data Science with Python'],
        "card_tokens": ['Applied Data Science with Python Specialization', 'University of Michigan'],
        "extra": [("answer_skills", n_ads >= 2, f"skills matched={n_ads}/4 of {sk_ads}")]},
        {"slug": "advanced-python-programming-specialization",
        "page_tokens": ['Advanced Python Programming Specialization', 'Skills'],
        "answer_tokens": ['Advanced Python Programming'],
        "card_tokens": ['Advanced Python Programming Specialization', 'Rice University'],
        "extra": [("answer_skills", n_adv >= 2, f"skills matched={n_adv}/4 of {sk_adv}")]},
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
