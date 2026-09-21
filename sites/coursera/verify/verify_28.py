#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--28.

Locate a Coursera Guided Project related to 'Astrophysics' suitable for advanced learners; mention the course duration, the institution, and the main subjects.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Analyzing Astrophysics Data with Python' (Johns Hopkins University, Guided Project, Advanced, Less Than 2 Hours; subjects: Astrophysics, Python, astropy, Data Analysis, matplotlib).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
guided-project navigation | page shows duration + subjects | answer names course + JHU + <2h + >=2 subjects
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
    j, t, fa = load_task(a, "Coursera--28")
    detail_page = page_text_at(t, "/learn/analyzing-astrophysics-data-python")
    card_page = page_text_at(t, "/search")
    via_detail = (navigated_to_course(t, "analyzing-astrophysics-data-python")
                  and contains_all(detail_page, ["Analyzing Astrophysics Data with Python",
                                                "Less Than 2 Hours"]))
    via_card = contains_all(card_page, ["Analyzing Astrophysics Data with Python",
                                     "Johns Hopkins University"])
    j.check("evidence_on_mirror", via_detail or via_card,
            ("course detail page" if via_detail else
             ("search results card" if via_card else
              "neither the guided-project page nor a search card shows the course")))
    j.check("answer_names_course", contains_all(fa, ["Analyzing Astrophysics Data with Python"]),
            f"final={fa[:160]!r}")
    j.check("answer_institution", contains_any(fa, ["Johns Hopkins", "JHU"]),
            "answer must name the institution")
    j.check("answer_duration",
            contains_any(fa, ["Less Than 2 Hours", "less than 2 hours", "under 2 hours",
                              "2 hours or less", "fewer than 2 hours"]),
            "answer must state the Less Than 2 Hours duration")
    subs = ["astrophysics", "python", "astropy", "data analysis", "matplotlib"]
    n_sub = sum(1 for s in subs if contains_all(fa, [s]))
    j.check("answer_subjects", n_sub >= 2, f"subjects matched={n_sub}/5 of {subs}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
