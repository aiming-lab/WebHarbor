#!/usr/bin/env python3
"""Verify Megabus--13.

Find the cheapest one-stop journey from New York to Boston departing at 9:00am on October 3rd. Which city does it connect through, what is the total travel time, and how does its fare compare with the 9:15am direct service on the same page? Open the one-stop's journey details and report where it boards in New York and where the connecting leg departs. I must be back in New York that evening: what is the last departure from Boston to New York that day, and what does it cost?
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_duration, contains_phrase, contains_time, final_answer,
                        navigated_journeys, run_verifier)

TASK_ID = "Megabus--13"
NY_ID, BOS_ID = 123, 94
DATE = "2026-10-03"
CONNECT_CITY = "Providence"
DURATION_MIN = 335
FARE = 44.99
DIRECT_FARE = 44.99
BOARDING_KEY = "Port Authority"
CONNECT_STOP_KEY = "Peter Pan Way"
LAST_DEP = "18:30"
LAST_FARE = 34.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_journeys_results",
                navigated_journeys(traj, NY_ID, BOS_ID, DATE),
                f"required: journeys NY->BOS on {DATE}")
    judge.check("visited_return_results",
                navigated_journeys(traj, BOS_ID, NY_ID, DATE),
                f"required: journeys BOS->NY on {DATE}")
    judge.check("answer_connect_city", contains_phrase(answer, CONNECT_CITY),
                f"expected the connection city {CONNECT_CITY!r}")
    judge.check("answer_travel_time", contains_duration(answer, DURATION_MIN),
                "expected total travel time 5h35m")
    judge.check("answer_fare", contains_amount(answer, FARE),
                f"expected the 9:00am one-stop fare ${FARE}")
    judge.check("answer_fare_comparison",
                contains_amount(answer, DIRECT_FARE)
                and (contains_phrase(answer, "same") or contains_phrase(answer, "equal")
                     or contains_phrase(answer, "identical")
                     or (contains_amount(answer, FARE) and contains_amount(answer, DIRECT_FARE))),
                "expected: the 9:15am direct service is also $44.99 — the fares are the same")
    judge.check("answer_ny_boarding", contains_phrase(answer, BOARDING_KEY),
                "expected the one-stop to board at the Port Authority Bus Terminal in New York")
    judge.check("answer_connect_stop", contains_phrase(answer, CONNECT_STOP_KEY),
                "expected the connecting leg to depart the Providence Bus Terminal "
                "(1 Peter Pan Way)")
    judge.check("answer_last_departure", contains_time(answer, LAST_DEP),
                f"expected the last BOS->NY departure {LAST_DEP} (6:30pm)")
    judge.check("answer_last_fare", contains_amount(answer, LAST_FARE),
                f"expected the last departure fare ${LAST_FARE}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
