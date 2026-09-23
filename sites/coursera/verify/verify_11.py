#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--11.

Search for a university-produced Specialization about project management and show a testimonial for it.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Engineering Project Management Specialization (Rice University; testimonials by Olusola Adebayo / Anna Mueller / Ahmed Hassan) and Project Management Principles and Practices Specialization (UC Irvine; testimonials by Priya Patel / Anna Mueller / Ahmed Hassan).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows a testimonial | answer names specialization + university + quotes a testimonial with its learner name
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
    j, t, fa = load_task(a, "Coursera--11")
    tm_rice = [("worth every minute", "Olusola Adebayo"),
               ("peer reviews and project work made the material stick", "Anna Mueller"),
               ("assignments were challenging in the right way", "Ahmed Hassan")]
    tm_uci = [("exceeded my expectations", "Priya Patel"),
              ("peer reviews and project work made the material stick", "Anna Mueller"),
              ("assignments were challenging in the right way", "Ahmed Hassan")]
    def _tm(pairs, tag):
        ok = any(contains_all(fa, [q]) and contains_all(fa, [nm]) for q, nm in pairs)
        return [(f"answer_shows_testimonial_{tag}", ok,
                "answer must quote a testimonial visible on the page together with its learner name")]
    opts = [
        {"slug": "engineering-project-management-specialization",
        "page_tokens": ['Engineering Project Management Specialization', 'Learner Testimonials'],
        "answer_tokens": ['Engineering Project Management', 'Rice University'],
        "extra": _tm(tm_rice, "rice")},
        {"slug": "project-management-principles-practices",
        "page_tokens": ['Project Management Principles and Practices Specialization', 'Learner Testimonials'],
        "answer_tokens": ['Project Management Principles and Practices', 'California, Irvine'],
        "extra": _tm(tm_uci, "uci")},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
