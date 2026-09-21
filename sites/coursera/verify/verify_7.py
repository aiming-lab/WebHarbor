#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--7.

Find a Reinforcement Learning course for Intermediate level with a rating of at least 4.5; provide name, institution, and number of reviews.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Reinforcement Learning Specialization (University of Michigan, 18,000 reviews) / Fundamentals of Reinforcement Learning (12,000) / Practical Reinforcement Learning (8,000) - all Intermediate, rating >= 4.5.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + institution + review count
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
    j, t, fa = load_task(a, "Coursera--7")
    rc = {"reinforcement-learning-specialization": 18000,
          "fundamentals-reinforcement-learning": 12000,
          "practical-reinforcement-learning": 8000}
    def _rc(slug):
        n = rc[slug]
        ok = counts(fa, n, "review", "reviews") or f"{n:,}" in fa \
             or re_found(fa, rf"\b{n // 1000}\s*k\b")
        return ("answer_review_count", ok, f"answer must state {n:,} reviews")
    extras = {s: [_rc(s)] for s in rc}
    opts = [
        {"slug": "reinforcement-learning-specialization",
        "page_tokens": ['Reinforcement Learning Specialization'],
        "answer_tokens": ['Reinforcement Learning Specialization', 'University of Michigan'],
        "card_tokens": ['Reinforcement Learning Specialization', 'University of Michigan'],
        "extra": extras["reinforcement-learning-specialization"]},
        {"slug": "fundamentals-reinforcement-learning",
        "page_tokens": ['Fundamentals of Reinforcement Learning'],
        "answer_tokens": ['Fundamentals of Reinforcement Learning', 'University of Michigan'],
        "card_tokens": ['Fundamentals of Reinforcement Learning', 'University of Michigan'],
        "extra": extras["fundamentals-reinforcement-learning"]},
        {"slug": "practical-reinforcement-learning",
        "page_tokens": ['Practical Reinforcement Learning'],
        "answer_tokens": ['Practical Reinforcement Learning', 'University of Michigan'],
        "card_tokens": ['Practical Reinforcement Learning', 'University of Michigan'],
        "extra": extras["practical-reinforcement-learning"]},
    ]
    via_detail = any(course_option_ok(t, fa, o) for o in opts)
    via_card = search_card_ok(t, fa, opts)
    if via_detail or via_card:
        j.evidence.append('[PASS] evidence_on_mirror: ' +
                          ('course detail page' if via_detail else 'search results card'))
    else:
        grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
