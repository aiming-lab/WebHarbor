#!/usr/bin/env python3
"""Verify Megabus--20.

I'm taking my first Megabus trip from New York to Boston on September 24, 2026. Find that day's first departure, its fare and boarding location, then help me prepare to board: explain what I must show the driver, where to find the reservation number, how early to arrive, and whether I may bring food. Identify the help pages supporting your advice.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, contains_time,
                        final_answer, navigated_journeys, run_verifier)

TASK_ID = "Megabus--20"
NY_ID, BOS_ID = 123, 94
SCHEDULE_DATE = "2026-09-24"
FIRST_DEP = "06:15"
FIRST_FARE = 53.99
BOARDING_KEY = "Port Authority"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_help_hub", "/help")
    check_visited_path(judge, traj, "visited_traveling_topic", "/help/traveling-on-the-bus")
    check_visited_path(judge, traj, "visited_boarding_topic",
                       "/help/customers-with-special-requirements")
    judge.check("visited_schedule_results",
                navigated_journeys(traj, NY_ID, BOS_ID, SCHEDULE_DATE),
                f"required: journeys NY->BOS on {SCHEDULE_DATE}")
    judge.check("answer_reservation_number",
                contains_phrase(answer, "reservation number"),
                "expected: show a valid reservation number to the driver")
    judge.check("answer_reservation_number_source",
                contains_phrase(answer, "confirmation page") or contains_phrase(answer, "confirmation"),
                "expected: the reservation number comes from the confirmation page after purchase")
    judge.check("answer_15_minutes", contains_count(answer, 15)
                and contains_phrase(answer, "minute"),
                "expected: arrive at least 15 minutes before departure")
    judge.check("answer_food_policy",
                (contains_phrase(answer, "snack") or contains_phrase(answer, "food"))
                and contains_phrase(answer, "alcohol"),
                "expected the food policy: snacks welcome, alcoholic beverages not permitted")
    judge.check("answer_cites_source",
                contains_phrase(answer, "help") or contains_phrase(answer, "faq"),
                "expected the answer to cite the help/FAQ pages as sources")
    judge.check("answer_first_departure", contains_time(answer, FIRST_DEP),
                f"expected the first departure {FIRST_DEP} (6:15am)")
    judge.check("answer_first_fare", contains_amount(answer, FIRST_FARE),
                f"expected the first departure fare ${FIRST_FARE}")
    judge.check("answer_boarding_stop", contains_phrase(answer, BOARDING_KEY),
                "expected the New York boarding stop Port Authority Bus Terminal")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
