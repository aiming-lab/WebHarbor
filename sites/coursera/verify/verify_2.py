#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--2.

Find the Beginner's Spanish Specialization on Coursera and show all the courses in this Specialization.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Learn Spanish: Basic Spanish Vocabulary Specialization' (UC Davis) contains exactly five courses: Spanish Vocabulary: Meeting People / Around Town / At Home / At Work / Nature and Environment.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows all five sub-courses | answer lists all five
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
    j, t, fa = load_task(a, "Coursera--2")
    page = page_text_at(t, "/learn/learn-spanish-basic-vocabulary-specialization")
    j.check("nav_specialization", navigated_to_course(t, "learn-spanish-basic-vocabulary-specialization"),
            "trajectory must open the Beginner Spanish Specialization page")
    subs = ["Spanish Vocabulary: Meeting People", "Spanish Vocabulary: Around Town",
            "Spanish Vocabulary: At Home", "Spanish Vocabulary: At Work",
            "Spanish Vocabulary: Nature and Environment"]
    j.check("page_shows_sub_courses", contains_all(page, subs),
            f"observed DOM must contain all five sub-course titles")
    missing = [s for s in subs if not contains_all(fa, [s])]
    j.check("answer_lists_all_sub_courses", not missing,
            f"answer must list all five courses; missing={missing}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
