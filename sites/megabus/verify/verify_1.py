#!/usr/bin/env python3
"""Verify Megabus--1.

I'm planning a weekend in Washington from New York: leave Friday October 2nd and come back Sunday October 4th, one traveler. Find the cheapest departure on each leg and report both fares, the combined total including the booking fee, and the total travel time of the outbound departure you would take. Check whether leaving Thursday October 1st or returning Monday October 5th would be cheaper, and report those fares too. Do not complete the checkout.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_duration, final_answer, navigated_journeys,
                        run_verifier)

TASK_ID = "Megabus--1"
NY_ID, WDC_ID = 123, 142
OUT_FARE, RET_FARE, BOOKING_FEE = 44.99, 49.99, 3.99
COMBINED = 98.97
THU_FARE = 39.99
MON_FARE = 35.99
OUT_DURATIONS_MIN = (260, 270, 280, 290, 300, 315, 380)  # every $44.99 outbound duration


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_outbound_results",
                navigated_journeys(traj, NY_ID, WDC_ID, "2026-10-02"),
                "required: /journey-planner/journeys?originId=123&destinationId=142&departureDate=2026-10-02")
    judge.check("visited_return_results",
                navigated_journeys(traj, WDC_ID, NY_ID, "2026-10-04"),
                "required: /journey-planner/journeys?originId=142&destinationId=123&departureDate=2026-10-04")
    judge.check("visited_thursday_results",
                navigated_journeys(traj, NY_ID, WDC_ID, "2026-10-01"),
                "required: journeys NY->WDC on 2026-10-01 (Thursday ribbon check)")
    judge.check("visited_monday_results",
                navigated_journeys(traj, WDC_ID, NY_ID, "2026-10-05"),
                "required: journeys WDC->NY on 2026-10-05 (Monday ribbon check)")
    judge.check("answer_outbound_fare", contains_amount(answer, OUT_FARE),
                f"expected outbound cheapest fare ${OUT_FARE}")
    judge.check("answer_return_fare", contains_amount(answer, RET_FARE),
                f"expected return cheapest fare ${RET_FARE}")
    judge.check("answer_combined_total", contains_amount(answer, COMBINED),
                f"expected combined total ${COMBINED} (fares + $3.99 booking fee)")
    judge.check("answer_outbound_duration",
                any(contains_duration(answer, m) for m in OUT_DURATIONS_MIN),
                f"expected the duration of the chosen $44.99 outbound departure "
                f"(one of {[f'{m//60}h{m%60:02d}m' for m in OUT_DURATIONS_MIN]})")
    judge.check("answer_reports_fare_breakdown", contains_amount(answer, BOOKING_FEE) or
                contains_amount(answer, COMBINED),
                "expected the booking fee or the combined-with-fee total in the answer")
    judge.check("answer_thursday_fare", contains_amount(answer, THU_FARE),
                f"expected the Thursday 2026-10-01 cheapest fare ${THU_FARE} (cheaper than Friday)")
    judge.check("answer_monday_fare", contains_amount(answer, MON_FARE),
                f"expected the Monday 2026-10-05 cheapest fare ${MON_FARE} (cheaper than Sunday)")
    # read-only task: no checkout navigation, DB unchanged
    judge.check("no_checkout", not any("/journey-planner/passenger-details" in u
                                      or "/journey-planner/payment" in u
                                      for u in (traj.get("steps") and [s.get("url", "") for s in traj["steps"]] or [])),
                "task says: do not complete the checkout")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
