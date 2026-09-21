#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--0.

Find a beginner-level online course about '3d printing' which lasts 1-3 months, provided by a renowned university.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 3D Printing Revolution / Introduction to 3D Printing Technology -> University of Illinois Urbana-Champaign; 3D Printing Applications -> University of California, Irvine (all Beginner, 1-3 Months).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
search + course-detail navigation | page shows the course | answer names course + university
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
    j, t, fa = load_task(a, "Coursera--0")
    opts = [
        {"slug": "3d-printing-revolution",
        "page_tokens": ['3D Printing Revolution'],
        "answer_tokens": ['3D Printing Revolution', 'University of Illinois'],
        "card_tokens": ['3D Printing Revolution', 'University of Illinois Urbana-Champaign'],},
        {"slug": "3d-printing-applications",
        "page_tokens": ['3D Printing Applications'],
        "answer_tokens": ['3D Printing Applications', 'California, Irvine'],
        "card_tokens": ['3D Printing Applications', 'University of California, Irvine'],},
        {"slug": "intro-3d-printing-technology",
        "page_tokens": ['Introduction to 3D Printing Technology'],
        "answer_tokens": ['Introduction to 3D Printing Technology', 'University of Illinois'],
        "card_tokens": ['Introduction to 3D Printing Technology', 'University of Illinois Urbana-Champaign'],},
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
