#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--30.

Locate 'Modern Art & Ideas' (The Museum of Modern Art); find the rounded percentage of 3-star ratings and which star level has the lowest percentage.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Rating breakdown on the course page: 5 stars 65%, 4 stars 22%, 3 stars 8%, 2 stars 3%, 1 star 2% -> 3-star = 8%, lowest = 1 star.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the rating breakdown | answer states 8% 3-star + 1-star lowest
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
    j, t, fa = load_task(a, "Coursera--30")
    page = page_text_at(t, "/learn/modern-art-ideas")
    j.check("nav_course", navigated_to_course(t, "modern-art-ideas"),
            "trajectory must open the Modern Art & Ideas page")
    j.check("page_shows_breakdown", contains_all(page, ["Modern Art & Ideas", "Rating Breakdown", "8%"]),
            "observed DOM must show the course rating breakdown")
    j.check("answer_three_star_pct", pct_of(fa, 8, "3"),
            "answer must state the 3-star percentage (8%)")
    j.check("answer_lowest_level", star_level_lowest(fa, 1),
            "answer must identify 1 star as the level with the lowest percentage")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
