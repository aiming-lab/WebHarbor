#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--17.

How many results are there for a search on Machine Learning, filtered by Credit Eligible and 1-4 Years duration?

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): search q=Machine Learning + credit=1 + duration=1-4_years returns exactly 2 results: Master of Science in Machine Learning (Georgia Tech) and Master of Engineering in Machine Learning and AI (Columbia).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
filtered search navigation (credit=1 + duration=1-4_years) | page shows both results | answer states 2
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
    j, t, fa = load_task(a, "Coursera--17")
    j.check("nav_filtered_search",
            navigated_to(t, "/search") and query_has(t, "credit=1")
            and query_has(t, "duration=1-4_years") and query_has(t, "machine learning"),
            "trajectory must include the Machine Learning search with Credit Eligible and 1-4 Years filters")
    page = page_text_at(t, "/search")
    j.check("page_shows_both_results",
            contains_all(page, ["Master of Science in Machine Learning",
                                "Master of Engineering in Machine Learning and AI"]),
            "filtered search page must show both degree results")
    j.check("answer_result_count", counts(fa, 2, "result", "results", "course", "courses",
                                           "degree", "degrees", "program", "programs", "match", "matches"),
            "answer must state that 2 results match")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
