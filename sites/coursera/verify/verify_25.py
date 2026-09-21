#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--25.

Find a beginner course about 'Relativity'; list the course's main topics and the estimated time in hours to complete it.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Understanding Einstein: The Special Theory of Relativity' (Stanford, Beginner, Approx. 18 hours; module topics: The Principle of Relativity, Special Theory of Relativity, Space-Time Diagrams, Time Dilation and Length Contraction, Mass-Energy Equivalence).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the modules | answer gives 18 hours + >=2 main topics
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
    j, t, fa = load_task(a, "Coursera--25")
    page = page_text_at(t, "/learn/understanding-einstein-special-relativity")
    j.check("nav_course", navigated_to_course(t, "understanding-einstein-special-relativity"),
            "trajectory must open the Understanding Einstein course page")
    j.check("page_shows_topics", contains_all(page, ["Understanding Einstein", "Time Dilation"]),
            "observed DOM must show the course and its module topics")
    topics = [["special relativity"], ["space time", "spacetime"], ["time dilation"],
              ["length contraction"], ["e=mc"], ["mass energy"], ["principle of relativity"]]
    n_top = sum(1 for g in topics if any(contains_all(fa, [a]) for a in g))
    j.check("answer_main_topics", n_top >= 2, f"topics matched={n_top} of {topics}")
    j.check("answer_hours", counts(fa, 18, "hour", "hours"),
            "answer must state the Approx. 18 hours duration")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
