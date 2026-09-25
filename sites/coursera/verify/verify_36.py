#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--36.

Browse Coursera: which universities offer Master of Advanced Study in Engineering degrees, and what is the latest application deadline for this degree?

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Master of Advanced Study in Engineering (Columbia University, deadline May 15, 2026); sibling engineering MAS degrees: MAS in Engineering Mechanics (UIUC, April 22, 2026), MAS in Engineering Sciences (Rice, March 31, 2026) -> latest deadline: May 15, 2026 (Columbia).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
degrees section navigation | page shows the MAS in Engineering + deadline | answer names Columbia + May 15, 2026
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
    j, t, fa = load_task(a, "Coursera--36")
    nav_deg = navigated_to(t, "/degrees") or navigated_to_course(t, "master-advanced-study-engineering-ucberkeley")
    j.check("nav_degrees_section", nav_deg,
            "trajectory must open the degrees section or the MAS Engineering degree page")
    page = page_text_at(t, "/degrees")
    inst = page_text_at(t, "/learn/master-advanced-study-engineering-ucberkeley")
    j.check("page_shows_mas_engineering",
            contains_all(page, ["Master of Advanced Study in Engineering", "May 15, 2026"])
            or contains_all(inst, ["Master of Advanced Study in Engineering", "May 15, 2026"]),
            "observed DOM must show the MAS in Engineering degree and its deadline")
    j.check("answer_university", contains_all(fa, ["Columbia"]),
            "answer must name Columbia University for the Master of Advanced Study in Engineering")
    j.check("answer_latest_deadline", contains_all(fa, ["May 15, 2026"]),
            "answer must state the latest application deadline (May 15, 2026)")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
