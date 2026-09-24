#!/usr/bin/env python3
"""Verify Megabus--12.

On Oct 3 New York->Boston: how many services run across the whole day, how
many involve a connection, the cheapest fare on the results page, and the
departure times of the two morning departures that require a connection; open
the first morning connection's journey details to name where it boards in New
York. Compare the reverse direction the same day (Boston->New York): how many
services run, how many involve a connection, and the cheapest fare.

Frozen ground truth (seed DB): NY->BOS 2026-10-03 = 15 services total; 6 are
connecting services (route BZ06-BZ03 via Providence: 06:30, 09:00, 10:30 —
each with a 44.99 and a 59.99 variant); cheapest fare $44.99. The two MORNING
connecting departure times are 06:30 and 09:00. The 06:30 one-stop boards at
the Port Authority Bus Terminal For Peter Pan (Gates 69-75) in New York.
BOS->NY 2026-10-03 = 18 services, 7 of them connections, cheapest fare
$34.99.
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
