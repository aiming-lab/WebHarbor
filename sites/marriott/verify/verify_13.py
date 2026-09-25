#!/usr/bin/env python3
"""Verify Marriott--13.

Free night in Miami 11/20/2026-11/21/2026 using the points-rate search: identify
the two properties with the lowest nightly points rates; open both hotels' rooms
pages and report each one's exact points rate and the nightly cash rate of its
cheapest room type; also report which of the two shows the higher average rating
on its reviews page.

Frozen ground truth (seed DB): lowest Miami points rates = citizenM Miami Brickell
(marsha MIABR, 17,000 pts/night, cheapest room $170, avg 4.1) and Element by
Marriott Miami Brickell (marsha MIAEK, 19,000 pts/night, cheapest room $190, avg
3.6); the higher-rated of the two is citizenM Miami Brickell.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_amount,
                        contains_phrase, final_answer, navigated_find_hotels, navigated_hotel_tab,
                        navigated_availability, run_verifier)

TASK_ID = "Marriott--13"
A = ("citizenM Miami Brickell", "MIABR", "citizenm-miami-brickell", 17000, 170, 4.1)
B = ("Element by Marriott Miami Brickell", "MIAEK", "element-miami-brickell", 19000, 190, 3.6)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_miami_points_search",
                navigated_find_hotels(traj, "Miami", {"useRewardsPoints": "true"}),
                "required: /search/findHotels.mi destinationAddress=Miami&useRewardsPoints=true")
    for name, marsha, slug, pts, cash, _avg in (A, B):
        judge.check(f"opened_rooms_{marsha}",
                    navigated_availability(traj, marsha) or navigated_hotel_tab(traj, "rooms", slug),
                    f"required: {name} rooms page opened")
        judge.check(f"visited_reviews_{marsha}", navigated_hotel_tab(traj, "reviews", slug),
                    f"required: {name} reviews page opened")
    judge.check("answer_a_name", contains_phrase(answer, "citizenM Miami Brickell"),
                "expected citizenM Miami Brickell among the two lowest-points properties")
    judge.check("answer_b_name", contains_phrase(answer, "Element by Marriott Miami Brickell"),
                "expected Element by Marriott Miami Brickell among the two lowest-points properties")
    judge.check("answer_a_points", contains_amount(answer, 17000),
                "expected citizenM Miami Brickell's 17,000 points/night rate")
    judge.check("answer_b_points", contains_amount(answer, 19000),
                "expected Element by Marriott Miami Brickell's 19,000 points/night rate")
    judge.check("answer_a_cash", contains_amount(answer, 170),
                "expected citizenM Miami Brickell's cheapest-room cash rate $170")
    judge.check("answer_b_cash", contains_amount(answer, 190),
                "expected Element by Marriott Miami Brickell's cheapest-room cash rate $190")
    judge.check("answer_higher_rating_verdict", contains_phrase(answer, "citizenM Miami Brickell"),
                "the higher-rated of the two is citizenM Miami Brickell (4.1 vs 3.6)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
