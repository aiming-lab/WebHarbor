#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--18.

Identify a Coursera course that teaches JavaScript, is beginner-friendly and includes a certificate upon completion.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): HTML, CSS, and Javascript for Web Developers (Johns Hopkins); JavaScript Algorithms and Data Structures (Meta); Programming with JavaScript (Meta); The Complete JavaScript Bootcamp (Meta); Meta Front-End Developer Professional Certificate (Meta) - all Beginner with a certificate.

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
    j, t, fa = load_task(a, "Coursera--18")
    opts = [
        {"slug": "html-css-javascript-web-developers",
        "page_tokens": ['HTML, CSS, and Javascript for Web Developers'],
        "answer_tokens": ['HTML, CSS', 'Javascript'],
        "card_tokens": ['HTML, CSS, and Javascript for Web Developers', 'Johns Hopkins University'],},
        {"slug": "javascript-algorithms-data-structures",
        "page_tokens": ['JavaScript Algorithms and Data Structures'],
        "answer_tokens": ['JavaScript Algorithms and Data Structures'],
        "card_tokens": ['JavaScript Algorithms and Data Structures', 'Meta'],},
        {"slug": "programming-javascript-meta",
        "page_tokens": ['Programming with JavaScript'],
        "answer_tokens": ['Programming with JavaScript'],
        "card_tokens": ['Programming with JavaScript', 'Meta'],},
        {"slug": "javascript-bootcamp",
        "page_tokens": ['The Complete JavaScript Bootcamp'],
        "answer_tokens": ['Complete JavaScript Bootcamp'],
        "card_tokens": ['The Complete JavaScript Bootcamp', 'Meta'],},
        {"slug": "meta-front-end-developer",
        "page_tokens": ['Meta Front-End Developer'],
        "answer_tokens": ['Meta Front-End Developer'],
        "card_tokens": ['Meta Front-End Developer Professional Certificate', 'Meta'],},
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
