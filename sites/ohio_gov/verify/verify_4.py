#!/usr/bin/env python3
"""Verify Ohio.gov--4.

Dolly Parton Day chain: the date and proclaiming governor, the Ohio program
that mails a free book each month to children under 5, and what the Assistance
Questions FAQ says about getting immediate help with food.

Frozen ground truth (tracked data snapshot): Governor Mike DeWine proclaimed
September 25, 2026 as Dolly Parton Day; the program is Dolly Parton's
Imagination Library of Ohio; the FAQ says the Ohio Association of Foodbanks
can help you find a foodbank serving your community (and Ohio's food
assistance program may also be able to help).
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_any, contains_phrase, final_answer, run_verifier)

TASK_ID = "Ohio.gov--4"
DOLLY_NEWS = "/news-and-events/all-news/gov.dolly-parton-day-sept26"
IMAGINATION_LIBRARY = "/residents/resources/dolly-partons-imagination-library-of-ohio"
ASSISTANCE_FAQ = "/help-center/faqs/assistance-programs"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the Dolly Parton Day article, the Imagination Library
    # resource page, and the Assistance Questions FAQ category
    check_visited_path(judge, traj, "visited_dolly_parton_day_article", DOLLY_NEWS)
    check_visited_path(judge, traj, "visited_imagination_library", IMAGINATION_LIBRARY)
    check_visited_path(judge, traj, "visited_assistance_faq", ASSISTANCE_FAQ)
    # answer: date, governor, program name, immediate food help
    judge.check("answer_dolly_day_date", contains_phrase(answer, "september 25"),
                "expected: September 25 (2026)")
    judge.check("answer_proclaiming_governor", contains_phrase(answer, "dewine"),
                "expected: Governor Mike DeWine")
    judge.check("answer_book_program",
                contains_phrase(answer, "imagination library"),
                "expected: Dolly Parton's Imagination Library of Ohio")
    judge.check("answer_immediate_food_help",
                contains_phrase(answer, "foodbank"),
                "expected: the Ohio Association of Foodbanks can help you find a foodbank")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
