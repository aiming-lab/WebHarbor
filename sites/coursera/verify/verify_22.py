#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--22.

Identify a Specialization that focuses on 'Human Resource'; list the courses included in it and the institution offering it.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Human Resource Management: HR for People Managers Specialization (University of Minnesota): Preparing to Manage Human Resources / Recruiting, Hiring, and Onboarding Employees / Managing Employee Performance / Managing Employee Compensation / Human Resources Management Capstone. Strategic Human Resource Leadership Specialization (Arizona State University): Strategic HR Foundations / Leading Organisational Change / HR Analytics for Executives / Capstone: Strategic HR Plan.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows the sub-courses | answer lists the sub-courses + institution
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
    j, t, fa = load_task(a, "Coursera--22")
    umn = [["Preparing to Manage Human Resources"], ["Recruiting", "Onboarding"],
          ["Employee Performance"], ["Employee Compensation"], ["Capstone"]]
    asu = [["Strategic HR Foundations"], ["Leading Organisational Change", "Leading Organizational Change"],
          ["HR Analytics"], ["Capstone"]]
    def groups_ok(groups):
        return all(any(contains_all(fa, alt) for alt in g) for g in groups)
    def groups_missing(groups):
        return [i for i, g in enumerate(groups) if not any(contains_all(fa, alt) for alt in g)]
    umn_ok = groups_ok(umn)
    asu_ok = groups_ok(asu)
    opts = [
        {"slug": "human-resource-management-specialization",
        "page_tokens": ['Human Resource Management: HR for People Managers Specialization'],
        "answer_tokens": ['University of Minnesota', 'HR for People Managers'],
        "extra": [("answer_lists_courses", umn_ok, f"answer must list every course; missing groups={groups_missing(umn)} of 5")]},
        {"slug": "strategic-human-resource-leadership-specialization",
        "page_tokens": ['Strategic Human Resource Leadership Specialization'],
        "answer_tokens": ['Arizona State', 'Strategic Human Resource'],
        "extra": [("answer_lists_courses", asu_ok, f"answer must list every course; missing groups={groups_missing(asu)} of 4")]},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
