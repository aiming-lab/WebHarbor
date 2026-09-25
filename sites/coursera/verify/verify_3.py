#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--3.

Identify a new course or Specialization related to Python Data Science, sort by newest, report the first course and its institution.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): search 'Python Data Science' sorted by Newest -> first result: 'Python for Data Science and Machine Learning' (IBM).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
search with sort=newest navigation | page shows the first course | answer names course + IBM
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
    j, t, fa = load_task(a, "Coursera--3")
    j.check("nav_search_newest", navigated_to(t, "/search") and query_has(t, "sort=newest"),
            "trajectory must include a /search URL with sort=newest")
    j.check("query_mentions_python", query_has(t, "python"),
            "the search query must mention python")
    opts = [
        {"slug": "python-data-science-ml-2024",
        "page_tokens": ['Python for Data Science and Machine Learning'],
        "answer_tokens": ['Python for Data Science', 'Machine Learning', 'IBM'],
        "card_tokens": ['Python for Data Science and Machine Learning', 'IBM'],},
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
