#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--31.

Search for 'Exploring Quantum Physics' (University of Maryland); identify the rounded percentage of 5-star ratings.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Rating breakdown on the course page: 5 stars 55%, 4 stars 28%, 3 stars 10%, 2 stars 4%, 1 star 3% -> 5-star = 55%.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the rating breakdown | answer states 55% 5-star
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
    j, t, fa = load_task(a, "Coursera--31")
    page = page_text_at(t, "/learn/exploring-quantum-physics")
    j.check("nav_course", navigated_to_course(t, "exploring-quantum-physics"),
            "trajectory must open the Exploring Quantum Physics page")
    j.check("page_shows_breakdown", contains_all(page, ["Exploring Quantum Physics", "Rating Breakdown", "55%"]),
            "observed DOM must show the course rating breakdown")
    j.check("answer_five_star_pct", pct_of(fa, 55, "5"),
            "answer must state the 5-star percentage (55%)")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
