#!/usr/bin/env python3
"""Verify Megabus--8.

First megabus trip New York -> Philadelphia on October 3rd, returning October
4th, general seating. Check both days' schedules: first departure after
6:00am each way with its fare. From the help center: the luggage allowance
for a general seating ticket, the exact condition for bicycles (size and
weight limits), and what happens if you miss your scheduled departure.

Frozen ground truth (seed DB): NY->PHL 2026-10-03 first after 06:00 = 06:30
@ $25.99; PHL->NY 2026-10-04 first after 06:00 = 06:30 @ $25.99. FAQ "What can
I bring with me?" (traveling-on-the-bus): one (1) piece of luggage and one
(1) carry-on bag with general seating tickets. Bicycle condition ("Can I take
my bicycles...?"): only inside a case that does not exceed the luggage
allowance — max 62 inches total exterior dimensions (L+W+H) and max 50
pounds. "What if I miss my schedule departure?": no refunds or credits are
given, but reservations can be changed on the website up until 6 hours prior
to departure.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, contains_time,
                        final_answer, navigated_journeys, run_verifier)

TASK_ID = "Megabus--8"
NY_ID, PHL_ID = 123, 127
OUT_DEP, OUT_FARE = "06:30", 25.99
RET_DEP, RET_FARE = "06:30", 25.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both days' schedules + the luggage/bicycle/missed-departure help topic
    judge.check("visited_outbound_results",
                navigated_journeys(traj, NY_ID, PHL_ID, "2026-10-03"),
                "required: journeys NY->PHL on 2026-10-03")
    judge.check("visited_return_results",
                navigated_journeys(traj, PHL_ID, NY_ID, "2026-10-04"),
                "required: journeys PHL->NY on 2026-10-04")
    check_visited_path(judge, traj, "visited_help_hub", "/help")
    check_visited_path(judge, traj, "visited_help_topic", "/help/traveling-on-the-bus")
    # answer: schedules both ways
    judge.check("answer_outbound_first_after_6am",
                contains_time(answer, OUT_DEP) and contains_amount(answer, OUT_FARE),
                f"expected the outbound first departure after 6am {OUT_DEP} @ ${OUT_FARE}")
    judge.check("answer_return_first_after_6am",
                contains_time(answer, RET_DEP) and contains_amount(answer, RET_FARE),
                f"expected the return first departure after 6am {RET_DEP} @ ${RET_FARE}")
    # answer: luggage + bicycle + missed departure
    judge.check("answer_luggage_allowance",
                contains_phrase(answer, "luggage") and contains_phrase(answer, "carry-on")
                and (contains_count(answer, 1) or contains_phrase(answer, "one ")),
                "expected: one piece of luggage and one carry-on bag")
    judge.check("answer_bicycle_condition",
                contains_phrase(answer, "case"),
                "bicycles are carried only inside a case")
    judge.check("answer_bicycle_size", contains_count(answer, 62),
                "expected the 62-inch total-dimensions case limit")
    judge.check("answer_bicycle_weight", contains_count(answer, 50),
                "expected the 50-pound case limit")
    judge.check("answer_missed_departure",
                (contains_phrase(answer, "no refund") or contains_phrase(answer, "no refunds"))
                and contains_count(answer, 6) and contains_phrase(answer, "hour"),
                "expected: no refunds or credits, but reservations can be changed up until "
                "6 hours prior to departure")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
