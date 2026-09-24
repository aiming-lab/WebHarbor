#!/usr/bin/env python3
"""Verify Megabus--12.

On October 3rd from New York to Boston: how many services run across the whole day, how many of them involve a connection, and what is the cheapest fare shown on the results page? Also report the departure times of the two morning departures that require a connection, and open the first one's journey details to name where it boards in New York. Compare the reverse direction the same day: how many services run from Boston to New York, how many involve a connection, and what is the cheapest fare?
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, contains_time, final_answer,
                        navigated_journeys, run_verifier)

TASK_ID = "Megabus--12"
NY_ID, BOS_ID = 123, 94
DATE = "2026-10-03"
TOTAL_SERVICES = 15
CONNECTIONS = 6
CHEAPEST = 44.99
MORNING_CONNECTIONS = ("06:30", "09:00")
BOARDING_KEY = "Port Authority"
REV_TOTAL = 18
REV_CONNECTIONS = 7
REV_CHEAPEST = 34.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_journeys_results",
                navigated_journeys(traj, NY_ID, BOS_ID, DATE),
                f"required: journeys NY->BOS on {DATE}")
    judge.check("visited_reverse_results",
                navigated_journeys(traj, BOS_ID, NY_ID, DATE),
                f"required: journeys BOS->NY on {DATE}")
    judge.check("answer_total_services", contains_count(answer, TOTAL_SERVICES),
                f"expected {TOTAL_SERVICES} services across the day")
    judge.check("answer_connections", contains_count(answer, CONNECTIONS),
                f"expected {CONNECTIONS} services with a connection")
    judge.check("answer_cheapest_fare", contains_amount(answer, CHEAPEST),
                f"expected cheapest fare ${CHEAPEST}")
    judge.check("answer_morning_connection_times",
                all(contains_time(answer, t) for t in MORNING_CONNECTIONS),
                f"expected morning connection departures {MORNING_CONNECTIONS}")
    judge.check("answer_first_connection_boarding", contains_phrase(answer, BOARDING_KEY),
                "expected the 6:30am connection to board at the Port Authority Bus Terminal in New York")
    judge.check("answer_reverse_total", contains_count(answer, REV_TOTAL),
                f"expected {REV_TOTAL} services from Boston to New York that day")
    judge.check("answer_reverse_connections", contains_count(answer, REV_CONNECTIONS),
                f"expected {REV_CONNECTIONS} Boston->New York services with a connection")
    judge.check("answer_reverse_cheapest", contains_amount(answer, REV_CHEAPEST),
                f"expected the Boston->New York cheapest fare ${REV_CHEAPEST}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
