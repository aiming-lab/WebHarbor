#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--4.

Identify a course or Specialization that helps business process management with a rating of 4.7.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Business Process Management (University of Queensland, 4.7); sibling 4.7-rated BPM courses: Operations Management: Business Process and Supply Chain (UIUC), Business Process Improvement (Vanderbilt).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + 4.7 rating
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
    j, t, fa = load_task(a, "Coursera--4")
    opts = [
        {"slug": "business-process-management",
        "page_tokens": ['Business Process Management'],
        "answer_tokens": ['Business Process Management', '4.7'],
        "card_tokens": ['Business Process Management', 'University of Queensland'],},
        {"slug": "operations-management-bpm",
        "page_tokens": ['Operations Management'],
        "answer_tokens": ['Operations Management', '4.7'],
        "card_tokens": ['Operations Management: Business Process and Supply Chain', 'University of Illinois Urbana-Champaign'],},
        {"slug": "business-process-improvement",
        "page_tokens": ['Business Process Improvement'],
        "answer_tokens": ['Business Process Improvement', '4.7'],
        "card_tokens": ['Business Process Improvement', 'Vanderbilt University'],},
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
