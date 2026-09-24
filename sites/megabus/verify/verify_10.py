#!/usr/bin/env python3
"""Verify Megabus--10.

From the Toronto city guide, list the top five things to do. Then check Oct 4
departures New York->Toronto: report the cheapest fare and how many departures
offer it that day. Check the Oct 5 return schedule Toronto->New York: how many
services run and the cheapest fare.

Frozen ground truth (seed DB): Toronto guide top five — Distillery District,
CN Tower, Hockey Hall of Fame, Toronto Zoo, ferry to the Toronto Islands.
NY->TOR 2026-10-04 has 3 departures (05:15, 17:15, 20:00), all at $80.05, so
the cheapest fare is offered by 3 departures. TOR->NY 2026-10-05 has 2
departures (08:00, 20:00), both at $80.05 (cheapest $80.05).
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_journeys, run_verifier)

TASK_ID = "Megabus--10"
NY_ID, TOR_ID = 123, 145
TOP5 = ("Distillery District", "CN Tower", "Hockey Hall of Fame", "Toronto Zoo", "Toronto Islands")
CHEAPEST = 80.05
OFFERING = 3
RET_COUNT = 2
RET_CHEAPEST = 80.05


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_city_guides_index", "/city-guides")
    check_visited_path(judge, traj, "visited_toronto_guide", "/city-guides/toronto")
    judge.check("visited_journeys_results",
                navigated_journeys(traj, NY_ID, TOR_ID, "2026-10-04"),
                "required: /journey-planner/journeys?originId=123&destinationId=145&departureDate=2026-10-04")
    judge.check("visited_return_results",
                navigated_journeys(traj, TOR_ID, NY_ID, "2026-10-05"),
                "required: journeys TOR->NY on 2026-10-05")
    hits = sum(1 for k in TOP5 if contains_phrase(answer, k))
    judge.check("answer_top5", hits >= 4,
                f"expected the guide's top five ({TOP5!r}); matched={hits}")
    judge.check("answer_cheapest_fare", contains_amount(answer, CHEAPEST),
                f"expected cheapest fare ${CHEAPEST}")
    judge.check("answer_offering_count", contains_count(answer, OFFERING),
                f"expected {OFFERING} departures at the cheapest fare")
    judge.check("answer_return_count", contains_count(answer, RET_COUNT),
                f"expected {RET_COUNT} return services on October 5th")
    judge.check("answer_return_cheapest", contains_amount(answer, RET_CHEAPEST),
                f"expected the October 5th return cheapest fare ${RET_CHEAPEST}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
