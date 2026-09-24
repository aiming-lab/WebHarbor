#!/usr/bin/env python3
"""Verify Megabus--14.

My friend takes the megabus from New York to Philadelphia on the morning of October 3rd and says the tracker shows a problem. Check the tracker for that route and date: which departure is delayed, by how many minutes, and when is it now expected to arrive? Open its live position and report where the bus is. Check the service alerts: does the Philadelphia alert affect her arrival? Then check the same day's schedule: what time is the next departure after the delayed one and what does it cost? What would the cheapest October 4th fare be if she rebooks?
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, contains_time,
                        final_answer, navigated_journeys, navigated_to, run_verifier)

TASK_ID = "Megabus--14"
NY_ID, PHL_ID = 123, 127
DELAYED_DEP = "08:45"
DELAY_MIN = 15
NEW_ARRIVAL = "11:00"
CURRENT_STOP_KEYS = ("Departed", "Port Authority")
NEXT_DEP = "09:45"
NEXT_FARE = 25.99
REBOOK_CHEAPEST = 25.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_tracker", "/journey-planner/track")
    judge.check("opened_live_position",
                navigated_to(traj, "journeyId="),
                "required: the delayed departure's live position was opened")
    check_visited_path(judge, traj, "visited_service_alerts", "/service-alerts")
    judge.check("visited_1003_schedule",
                navigated_journeys(traj, NY_ID, PHL_ID, "2026-10-03"),
                "required: journeys NY->PHL on 2026-10-03")
    judge.check("visited_1004_schedule",
                navigated_journeys(traj, NY_ID, PHL_ID, "2026-10-04"),
                "required: journeys NY->PHL on 2026-10-04 (rebooking fare)")
    judge.check("answer_delayed_departure", contains_time(answer, DELAYED_DEP),
                f"expected the delayed {DELAYED_DEP} departure")
    judge.check("answer_delay_minutes", contains_count(answer, DELAY_MIN),
                f"expected a {DELAY_MIN}-minute delay")
    judge.check("answer_new_arrival", contains_time(answer, NEW_ARRIVAL),
                f"expected the revised arrival {NEW_ARRIVAL} (11:00am)")
    judge.check("answer_says_delayed", contains_phrase(answer, "delay"),
                "expected the answer to state the departure is delayed")
    judge.check("answer_current_position",
                all(contains_phrase(answer, k) for k in CURRENT_STOP_KEYS),
                "expected the live position 'Departed New York, NY - Port Authority Bus Terminal'")
    judge.check("answer_arrival_unaffected",
                contains_phrase(answer, "arrival") and
                (contains_phrase(answer, "not affected") or contains_phrase(answer, "unaffected")),
                "the alert moves the departing stop; arrivals are not affected")
    judge.check("answer_next_departure", contains_time(answer, NEXT_DEP),
                f"expected the next departure after the delayed one {NEXT_DEP} (9:45am)")
    judge.check("answer_next_fare", contains_amount(answer, NEXT_FARE),
                f"expected the next departure fare ${NEXT_FARE}")
    judge.check("answer_rebook_cheapest", contains_amount(answer, REBOOK_CHEAPEST),
                f"expected the October 4th cheapest fare ${REBOOK_CHEAPEST}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
