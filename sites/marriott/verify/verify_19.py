#!/usr/bin/env python3
"""Verify Marriott--19.

Open the Special Offers page and report the title of the offer whose book-by date
is 12/20/2026 and the bonus points amount its blurb mentions; then search Chicago
hotels for 12/05/2026-12/06/2026 filtered to the Courtyard brand and report how
many properties appear and the nightly rate of the cheapest one; repeat the same
brand-filtered search for Orlando the same dates and report how many Courtyard
hotels appear there.

Frozen ground truth (seed DB): the only offer with book-by 12/20/2026 =
"Resort Rewards: 5,000 Bonus Points Daily" (blurb: 5,000 bonus points per day);
Chicago Courtyard = exactly 1 property, Courtyard by Marriott Chicago Downtown/
River North at $265/night; Orlando Courtyard = exactly 1 property (Courtyard by
Marriott Orlando Downtown).
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_find_hotels, run_verifier)

TASK_ID = "Marriott--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_offers_page", "/offers.mi")
    judge.check("visited_chicago_courtyard_search",
                navigated_find_hotels(traj, "Chicago", {"brand": "CY"}),
                "required: /search/findHotels.mi destinationAddress=Chicago&brand=CY")
    judge.check("visited_orlando_courtyard_search",
                navigated_find_hotels(traj, "Orlando", {"brand": "CY"}),
                "required: /search/findHotels.mi destinationAddress=Orlando&brand=CY")
    # answer facts
    judge.check("answer_offer_title",
                contains_phrase(answer, "Resort Rewards: 5,000 Bonus Points Daily"),
                "expected the offer title 'Resort Rewards: 5,000 Bonus Points Daily'")
    judge.check("answer_bonus_points", contains_amount(answer, 5000),
                "expected the 5,000 bonus points amount from the blurb")
    judge.check("answer_chicago_count", contains_count(answer, 1),
                "expected exactly 1 Courtyard property in Chicago")
    judge.check("answer_chicago_cheapest_rate", contains_amount(answer, 265),
                "expected the Chicago Courtyard nightly rate $265")
    judge.check("answer_orlando_count", contains_count(answer, 1),
                "expected exactly 1 Courtyard property in Orlando")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
