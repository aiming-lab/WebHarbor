#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--24.

Locate a Sustainability course in the Physical Science and Engineering subject that includes a module on Measuring Sustainability; note the course duration and the offering institution.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Sustainability and Development' (University of Michigan, Approx. 14 hours) is the Physical Science and Engineering sustainability course whose Week 2 module is 'Measuring Sustainability'.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the Measuring Sustainability module | answer names duration + institution
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
    j, t, fa = load_task(a, "Coursera--24")
    opts = [
        {"slug": "sustainability-and-development",
        "page_tokens": ['Sustainability and Development', 'Measuring Sustainability'],
        "answer_tokens": ['Sustainability and Development', 'Michigan'],
        "card_tokens": ['Sustainability and Development', 'University of Michigan'],},
    ]
    via_detail = any(course_option_ok(t, fa, o) for o in opts)
    via_card = search_card_ok(t, fa, opts)
    if via_detail or via_card:
        j.evidence.append('[PASS] evidence_on_mirror: ' +
                          ('course detail page' if via_detail else 'search results card'))
    else:
        grade_options(j, t, fa, opts)

    j.check("answer_duration_hours", counts(fa, 14, "hour", "hours"),
            "answer must state the Approx. 14 hours duration")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
