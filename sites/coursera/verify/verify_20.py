#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--20.

Find an Intermediate-level course about 'Blockchain Technology' lasting 1 to 4 weeks from a well-known institution; note the main goals and the instructor.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Blockchain Basics (University at Buffalo, Bina Ramamurthy); Blockchain Technology (University at Buffalo, Bina Ramamurthy); Introduction to Blockchain Technology (University of Michigan, Don Tapscott) - all Intermediate, 1-4 Weeks.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + instructor + a main goal
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
    j, t, fa = load_task(a, "Coursera--20")
    goals_bb = ["Understand blockchain technology", "Explain Bitcoin architecture",
               "Describe smart contracts", "Analyse consensus mechanisms"]
    goals_bt = ["Explain distributed ledger technology", "Implement basic smart contracts",
                "Design blockchain solutions", "Evaluate security tradeoffs"]
    goals_ib = ["Understand blockchain architecture", "Explain smart contracts", "Evaluate DeFi"]
    n_bb = sum(1 for g in goals_bb if contains_all(fa, [g]))
    n_bt = sum(1 for g in goals_bt if contains_all(fa, [g]))
    n_ib = sum(1 for g in goals_ib if contains_all(fa, [g]))
    opts = [
        {"slug": "blockchain-basics",
        "page_tokens": ['Blockchain Basics'],
        "answer_tokens": ['Blockchain Basics', 'Bina Ramamurthy'],
        "extra": [("answer_goals", n_bb >= 1, f"goals matched={n_bb} of {goals_bb}")]},
        {"slug": "blockchain-technology",
        "page_tokens": ['Blockchain Technology'],
        "answer_tokens": ['Blockchain Technology', 'Bina Ramamurthy'],
        "extra": [("answer_goals", n_bt >= 1, f"goals matched={n_bt} of {goals_bt}")]},
        {"slug": "introduction-blockchain-technology",
        "page_tokens": ['Introduction to Blockchain Technology'],
        "answer_tokens": ['Introduction to Blockchain Technology', 'Don Tapscott'],
        "extra": [("answer_goals", n_ib >= 1, f"goals matched={n_ib} of {goals_ib}")]},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
