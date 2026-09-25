#!/usr/bin/env python3
"""Verify Public Storage--19 (read-only) — r2 task text.

Open the facility at 1213 W 6th Street in Austin and read its customer
reviews. Report the names, star ratings, and review dates of the two most
recent reviewers shown, plus the facility's overall rating, total review
count, and phone number. Also report the facility's cheapest listed unit
size, that unit's online rate, and its promotion.

Frozen ground truth (seed DB): facility 809 (1213 W 6th Street, Austin TX)
is rated 4.3 with 516 reviews, phone 512-524-9545. Its two most recent
reviewers as displayed are Cynthia Guerrero (5 stars, 2026-09-17) and
Travis Smith (5 stars, 2026-08-22). Its cheapest listed unit is a 5'x5' at
$68/mo online with promotion $1 FIRST MONTH RENT.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_any_phrase, contains_count,
                        contains_phrase, final_answer, navigated_facility,
                        navigated_zip_search, run_verifier)

TASK_ID = "Public Storage--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_facility_809", navigated_facility(traj, 809),
                "required: 1213 W 6th Street Austin facility page with reviews")
    # the two most recent reviewers
    judge.check("answer_reviewer_1", contains_phrase(answer, "Cynthia Guerrero"),
                "most recent reviewer: Cynthia Guerrero")
    judge.check("answer_reviewer_1_stars",
                contains_any_phrase(answer, ["5 stars", "five stars", "★★★★★"]),
                "Cynthia Guerrero rated 5 stars")
    judge.check("answer_reviewer_1_date",
                contains_phrase(answer, "2026-09-17")
                or contains_phrase(answer, "september 17, 2026")
                or contains_phrase(answer, "sep 17"),
                "Cynthia Guerrero's review dated 2026-09-17")
    judge.check("answer_reviewer_2", contains_phrase(answer, "Travis Smith"),
                "second most recent reviewer: Travis Smith")
    judge.check("answer_reviewer_2_stars",
                contains_any_phrase(answer, ["5 stars", "five stars", "★★★★★"]),
                "Travis Smith rated 5 stars")
    judge.check("answer_reviewer_2_date",
                contains_phrase(answer, "2026-08-22")
                or contains_phrase(answer, "august 22, 2026")
                or contains_phrase(answer, "aug 22"),
                "Travis Smith's review dated 2026-08-22")
    # facility facts
    judge.check("answer_overall_rating", contains_phrase(answer, "4.3"),
                "overall rating 4.3")
    judge.check("answer_review_count", contains_count(answer, 516),
                "total review count 516")
    judge.check("answer_phone", contains_phrase(answer, "512-524-9545"),
                "facility phone 512-524-9545")
    # cheapest listed unit
    judge.check("answer_cheapest_size",
                contains_phrase(answer, "5'x5'") or contains_phrase(answer, "5x5")
                or contains_phrase(answer, "5 x 5"),
                "cheapest listed unit size 5'x5'")
    judge.check("answer_cheapest_rate", contains_amount(answer, 68),
                "cheapest listed unit online rate $68")
    judge.check("answer_cheapest_promo", contains_phrase(answer, "first month rent"),
                "cheapest unit promotion $1 FIRST MONTH RENT")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
