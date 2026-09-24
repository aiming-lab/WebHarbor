#!/usr/bin/env python3
"""Verify Megabus--7.

From the Boston to New York route guide: the fastest travel time, how many
services run per day, and at which named locations the bus boards in Boston
and drops off in New York. Then check the October 3rd schedule from Boston to
New York: first departure of the day and its fare. And the October 4th
schedule from New York to Boston: how many services run and the cheapest fare.

The guide is reachable via the home page's Top bus routes chips or the route
guides index; the guide page itself is the gated surface.

Frozen ground truth (seed DB): route guide slug boston-to-new-york-bus —
fastest time 4 hours 20 minutes; up to 37 services per day. Boston boarding:
Peter Pan Bus Lines bus stop at Boston (South Station) - 700 Atlantic Avenue.
New York drop-off: Port Authority Bus Terminal. BOS->NY 2026-10-03 first
departure = 06:00 @ $34.99. NY->BOS 2026-10-04 = 19 services, cheapest fare
$44.99.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_duration, contains_phrase,
                        contains_time, final_answer, navigated_journeys, run_verifier)

TASK_ID = "Megabus--7"
SLUG = "boston-to-new-york-bus"
FASTEST_MIN = 260
SERVICES = 37
BOS_ID, NY_ID = 94, 123
FIRST_DEP = "06:00"
FIRST_FARE = 34.99
RETURN_COUNT = 19
RETURN_CHEAPEST = 44.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_route_guide", f"/route-guides/{SLUG}")
    judge.check("answer_fastest_time", contains_duration(answer, FASTEST_MIN),
                "expected fastest travel time 4 hours 20 minutes")
    judge.check("answer_services_per_day", contains_count(answer, SERVICES),
                f"expected up to {SERVICES} services per day")
    judge.check("answer_boston_boarding",
                contains_phrase(answer, "South Station") and contains_phrase(answer, "Atlantic"),
                "expected Boston boarding at South Station - 700 Atlantic Avenue")
    judge.check("answer_ny_dropoff", contains_phrase(answer, "Port Authority"),
                "expected the New York drop-off at the Port Authority Bus Terminal")
    # October 3rd BOS->NY schedule check
    judge.check("visited_bos_ny_1003_results",
                navigated_journeys(traj, BOS_ID, NY_ID, "2026-10-03"),
                "required: journeys BOS->NY on 2026-10-03")
    judge.check("answer_first_departure", contains_time(answer, FIRST_DEP),
                f"expected the first departure of the day {FIRST_DEP} (6:00am)")
    judge.check("answer_first_fare", contains_amount(answer, FIRST_FARE),
                f"expected the first departure fare ${FIRST_FARE}")
    # October 4th NY->BOS return check
    judge.check("visited_ny_bos_1004_results",
                navigated_journeys(traj, NY_ID, BOS_ID, "2026-10-04"),
                "required: journeys NY->BOS on 2026-10-04")
    judge.check("answer_return_count", contains_count(answer, RETURN_COUNT),
                f"expected {RETURN_COUNT} services on the October 4th return")
    judge.check("answer_return_cheapest", contains_amount(answer, RETURN_CHEAPEST),
                f"expected the October 4th return cheapest fare ${RETURN_CHEAPEST}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
