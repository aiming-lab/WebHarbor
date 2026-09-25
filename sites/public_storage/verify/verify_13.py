#!/usr/bin/env python3
"""Verify Public Storage--13 (read-only) — r2 task text.

My partner is being deployed and we need to store our household goods near
Charlotte. What does the military storage solutions page say Public Storage
offers military personnel and their families? Then find the highest-rated
Charlotte facility and report its street address, rating, total review
count, and phone number, plus its cheapest currently listed unit size with
that unit's online rate, in-store price, and promotion, and whether the
facility offers drive-up access.

Frozen ground truth (seed DB): the military storage page says Public Storage
offers military personnel and their families a flexible, convenient way to
store belongings. The highest-rated Charlotte facility is 1001 N Tryon St
(facility 2334), rated 4.8 with 533 reviews, phone 704-266-1406; its
cheapest listed unit is a 5'x10' at $71/mo online ($79 in store, promotion
$1 FIRST MONTH RENT) and the facility offers Drive-Up Access.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_facility, navigated_solution, navigated_zip_search,
                        run_verifier)

TASK_ID = "Public Storage--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_military_page", navigated_solution(traj, "military-storage"),
                "required: the military storage solutions page")
    judge.check("visited_charlotte_search", navigated_zip_search(traj, "charlotte"),
                "required: Charlotte search results")
    judge.check("visited_facility_2334", navigated_facility(traj, 2334),
                "required: the highest-rated Charlotte facility (1001 N Tryon St)")
    # military page fact
    judge.check("answer_military_offer",
                contains_phrase(answer, "flexible") and contains_phrase(answer, "convenient"),
                "a flexible, convenient way to store belongings")
    # facility facts
    judge.check("answer_address", contains_phrase(answer, "1001 N Tryon St"),
                "highest-rated facility 1001 N Tryon St")
    judge.check("answer_rating", contains_phrase(answer, "4.8"),
                "facility rating 4.8")
    judge.check("answer_review_count", contains_count(answer, 533),
                "total review count 533")
    judge.check("answer_phone", contains_phrase(answer, "704-266-1406"),
                "facility phone 704-266-1406")
    # cheapest listed unit
    judge.check("answer_cheapest_size",
                contains_phrase(answer, "5'x10'") or contains_phrase(answer, "5x10")
                or contains_phrase(answer, "5 x 10"),
                "cheapest listed unit size 5'x10'")
    judge.check("answer_cheapest_rate", contains_amount(answer, 71),
                "cheapest unit online rate $71")
    judge.check("answer_cheapest_instore", contains_amount(answer, 79),
                "cheapest unit in-store price $79")
    judge.check("answer_cheapest_promo", contains_phrase(answer, "first month rent"),
                "cheapest unit promotion $1 FIRST MONTH RENT")
    judge.check("answer_drive_up",
                contains_phrase(answer, "drive-up") or contains_phrase(answer, "drive up"),
                "the facility offers drive-up access")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
