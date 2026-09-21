#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--37.

Browse the Coursera homepage and list at least three free courses.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Free courses on the mirror (homepage free section + free search): Introduction to Psychology; Modern Art & Ideas; Programming for Everybody (Getting Started with Python); R Programming; R for Data Science and Machine Learning; Fundamentals of Digital Marketing; The Science of Well-Being; Learning How to Learn; Financial Markets; Introduction to Generative AI; What is Data Science?; Python Basics for Beginners; Personal Sustainability Habits and Mindful Living; Statistics with R Specialization; Data Science: R Basics; Blockchain Technology Executive Briefing; JavaScript Foundations Quick Tour.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
homepage navigation | answer lists >=3 of the free course titles
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
    j, t, fa = load_task(a, "Coursera--37")
    home = any(is_mirror_url(u) and _url_path(u) in ("/", "") for u in step_urls(t))
    j.check("nav_homepage", home, "trajectory must include the Coursera homepage")
    free = ["Introduction to Psychology", "Modern Art & Ideas",
            "Programming for Everybody", "R Programming",
            "R for Data Science and Machine Learning", "Fundamentals of Digital Marketing",
            "The Science of Well-Being", "Learning How to Learn", "Financial Markets",
            "Introduction to Generative AI", "What is Data Science?",
            "Python Basics for Beginners", "Personal Sustainability Habits",
            "Statistics with R Specialization", "Data Science: R Basics",
            "Blockchain Technology Executive Briefing", "JavaScript Foundations Quick Tour"]
    found = [c for c in free if contains_all(fa, [c])]
    j.check("answer_lists_three_free_courses", len(found) >= 3,
            f"free courses found={found}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
