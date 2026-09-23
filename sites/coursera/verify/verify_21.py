#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--21.

Search for a beginner-level online course about 'Digital Marketing'; specify the course duration, the main learning outcomes, and the institution.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Fundamentals of Digital Marketing (Google, Approx. 40 hours, free; outcomes: Create a digital marketing strategy, Optimize for search engines, Run social media campaigns, Use Google Analytics) or Digital Marketing Specialization (University of Illinois, 8 Months; outcomes: Design a digital marketing strategy, Create content campaigns, Manage social media, Analyse marketing data).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + duration + institution + an outcome
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
    j, t, fa = load_task(a, "Coursera--21")
    out_g = ["Create a digital marketing strategy", "Optimize for search engines",
             "Run social media campaigns", "Use Google Analytics"]
    out_u = ["Design a digital marketing strategy", "Create content campaigns",
             "Manage social media", "Analyse marketing data"]
    n_g = sum(1 for o in out_g if contains_all(fa, [o]))
    n_u = sum(1 for o in out_u if contains_all(fa, [o]))
    opts = [
        {"slug": "fundamentals-digital-marketing",
        "page_tokens": ['Fundamentals of Digital Marketing'],
        "answer_tokens": ['Fundamentals of Digital Marketing', 'Google'],
        "extra": [("answer_duration", counts(fa, 40, "hour", "hours"), "answer must state the Approx. 40 hours duration"), ("answer_outcomes", n_g >= 1, f"outcomes matched={n_g} of {out_g}")]},
        {"slug": "digital-marketing-specialization",
        "page_tokens": ['Digital Marketing Specialization'],
        "answer_tokens": ['Digital Marketing Specialization', 'Illinois'],
        "extra": [("answer_duration", counts(fa, 8, "month", "months"), "answer must state the 8 Months duration"), ("answer_outcomes", n_u >= 1, f"outcomes matched={n_u} of {out_u}")]},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
