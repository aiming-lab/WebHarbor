#!/usr/bin/env python3
"""Verify Megabus--9.

I'm traveling from Albany to New York on October 3rd and returning October 4th. First check the bus stops page: which company operates the most stops listed under Albany, NY, how many Albany stops does it serve, and what are they named? Then check the October 3rd schedule from Albany to New York: how many services run, what does the first departure cost, and where does it board in Albany? And how many services make the return trip on October 4th?
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, contains_time,
                        final_answer, navigated_journeys, run_verifier)

TASK_ID = "Megabus--9"
ALB_ID, NY_ID = 89, 123
CARRIER = "Adirondack Trailways"
STOP_KEYS = ("66 Green Street", "737 Albany Shaker Rd", "1400 Washington Ave")
OUT_COUNT = 11
OUT_FIRST_FARE = 32.06
OUT_FIRST_DEP = "04:10"
BOARDING_KEY = "66 Green Street"
RET_COUNT = 23


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_stops_index", "/stops")
    check_visited_path(judge, traj, "visited_albany_stops", "/stops/albany")
    judge.check("visited_alb_ny_1003_results",
                navigated_journeys(traj, ALB_ID, NY_ID, "2026-10-03"),
                "required: journeys ALB->NY on 2026-10-03")
    judge.check("visited_ny_alb_1004_results",
                navigated_journeys(traj, NY_ID, ALB_ID, "2026-10-04"),
                "required: journeys NY->ALB on 2026-10-04")
    # answer: carrier + stops (from the stops pages)
    judge.check("answer_carrier", contains_phrase(answer, CARRIER),
                f"expected carrier {CARRIER!r}")
    judge.check("answer_stop_count", contains_count(answer, 3),
                "expected 3 Albany stops for the carrier")
    named = sum(1 for k in STOP_KEYS if contains_phrase(answer, k))
    judge.check("answer_names_stops", named >= 2,
                f"expected the carrier's stop locations (>=2 of {STOP_KEYS!r}); matched={named}")
    # answer: schedule facts
    judge.check("answer_outbound_count", contains_count(answer, OUT_COUNT),
                f"expected {OUT_COUNT} services from Albany to New York on October 3rd")
    judge.check("answer_first_departure_cost", contains_amount(answer, OUT_FIRST_FARE),
                f"expected the first departure fare ${OUT_FIRST_FARE}")
    judge.check("answer_first_departure_time", contains_time(answer, OUT_FIRST_DEP),
                f"expected the first departure {OUT_FIRST_DEP} (4:10am)")
    judge.check("answer_boarding_stop", contains_phrase(answer, BOARDING_KEY),
                "expected the Albany boarding stop 66 Green Street from the journey details")
    judge.check("answer_return_count", contains_count(answer, RET_COUNT),
                f"expected {RET_COUNT} return services on October 4th")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
