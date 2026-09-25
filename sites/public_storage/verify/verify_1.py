#!/usr/bin/env python3
"""Verify Public Storage--1 (read-only) — r2 task text.

Check the size guide's comparison chart for which unit size fits a
three-bedroom home and how many square feet that is, then find the cheapest
10'x20' inside unit (an indoor unit inside the facility, not an outside,
drive-up, or vehicle parking space) in Denver and report the facility's
street address and its online rate.

Frozen ground truth (seed DB): the comparison chart maps 10'x20' to a
3 Bedroom home at 200 sq ft. Denver's cheapest indoor (Inside Unit) 10'x20'
is V_1521980 at $205/mo online at 400 W Center Ave (facility 2387); the
cheaper $192 10'x20' at 680 Sheridan Blvd is an outside drive-up unit, and the
10'x20' vehicle spaces are excluded by the task.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_facility, navigated_size_guide, navigated_zip_search,
                        run_verifier)

TASK_ID = "Public Storage--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_size_guide", navigated_size_guide(traj),
                "required: size-guide hub with the comparison chart")
    judge.check("visited_denver_search", navigated_zip_search(traj, "denver"),
                "required: Denver search results")
    judge.check("visited_facility_2387", navigated_facility(traj, 2387),
                "required: facility page of the cheapest indoor 10x20 (400 W Center Ave)")
    judge.check("answer_chart_size", contains_phrase(answer, "10'x20'")
                or contains_phrase(answer, "10x20") or contains_phrase(answer, "10 x 20"),
                "the chart row fitting a 3-bedroom home is 10'x20'")
    judge.check("answer_chart_fits", contains_phrase(answer, "3 bedroom")
                or contains_phrase(answer, "three bedroom") or contains_phrase(answer, "three-bedroom"),
                "the chart says 10'x20' fits a 3 Bedroom home")
    judge.check("answer_chart_sqft", contains_count(answer, 200),
                "200 square feet")
    judge.check("answer_address", contains_phrase(answer, "400 W Center Ave"),
                "facility street address 400 W Center Ave")
    judge.check("answer_online_rate", contains_amount(answer, 205),
                "online rate $205")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
