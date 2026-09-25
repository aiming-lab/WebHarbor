#!/usr/bin/env python3
"""Verify Public Storage--8 (read-only) — r2 task text.

On the Chicago city page, what is the average cost of a storage unit, what
is the cheapest unit currently listed, and how many Chicago locations does
the page show? Which Chicago facility has the most customer reviews, and how
many? Report that facility's street address, rating, and phone number, plus
its cheapest currently listed unit size and that unit's online rate.

Frozen ground truth (seed DB): the Chicago city page shows an average cost
of $160, cheapest unit $50, 10 locations. The most-reviewed facility is
3659 S Ashland Ave (facility 1345) with 869 reviews, rated 4.7, phone
773-920-1940; its cheapest listed unit is a 5'x5' at $65/mo online.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_city_page, navigated_facility, run_verifier)

TASK_ID = "Public Storage--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_chicago_city_page", navigated_city_page(traj, "il-chicago"),
                "required: the Chicago city page")
    judge.check("visited_facility_1345", navigated_facility(traj, 1345),
                "required: the most-reviewed facility (3659 S Ashland Ave)")
    # city page stats
    judge.check("answer_average_cost", contains_amount(answer, 160),
                "average cost of a storage unit $160")
    judge.check("answer_cheapest_listed", contains_amount(answer, 50),
                "cheapest unit currently listed $50")
    judge.check("answer_location_count", contains_count(answer, 10),
                "10 Chicago locations shown")
    # most-reviewed facility
    judge.check("answer_most_reviewed", contains_phrase(answer, "3659 S Ashland Ave"),
                "most-reviewed facility 3659 S Ashland Ave")
    judge.check("answer_review_count", contains_count(answer, 869),
                "869 customer reviews")
    judge.check("answer_rating", contains_phrase(answer, "4.7"),
                "facility rating 4.7")
    judge.check("answer_phone", contains_phrase(answer, "773-920-1940"),
                "facility phone 773-920-1940")
    # cheapest listed unit at that facility
    judge.check("answer_cheapest_size",
                contains_phrase(answer, "5'x5'") or contains_phrase(answer, "5x5")
                or contains_phrase(answer, "5 x 5"),
                "cheapest listed unit size 5'x5'")
    judge.check("answer_cheapest_rate", contains_amount(answer, 65),
                "cheapest listed unit online rate $65")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
