#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--41.

Browse the online degrees section on Coursera and list 3 Bachelor's degree programmes.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Bachelor's degrees on the mirror: BSc Computer Science (University of London); Bachelor of Applied Arts and Sciences (Arizona State University); Bachelor of Arts in Communication (Vanderbilt University); Bachelor of Science in Business Administration (Arizona State University); Bachelor of Science in Data Science (Arizona State University); Bachelor of Science in Information Technology (University of Illinois Urbana-Champaign).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
degrees section navigation | page shows the bachelor cards | answer lists >=3 bachelor programme titles
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
    j, t, fa = load_task(a, "Coursera--41")
    j.check("nav_degrees_section", navigated_to(t, "/degrees"),
            "trajectory must open the online degrees section")
    page = page_text_at(t, "/degrees")
    bachelors = ["BSc Computer Science", "Bachelor of Applied Arts and Sciences",
                "Bachelor of Arts in Communication",
                "Bachelor of Science in Business Administration",
                "Bachelor of Science in Data Science",
                "Bachelor of Science in Information Technology"]
    j.check("page_shows_bachelors", contains_all(page, bachelors),
            "degrees page DOM must show the Bachelor degree programmes")
    found = [b for b in bachelors if contains_all(fa, [b])]
    j.check("answer_lists_three_bachelors", len(found) >= 3,
            f"bachelor programmes found={found}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
