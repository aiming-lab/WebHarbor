#!/usr/bin/env python3
"""Verify Megabus--6.

Help me choose a low-cost day trip from Philadelphia on October 3rd. Compare the fare finder's three cheapest destinations by starting fare and travel time, then check the cheapest destination's actual morning departures that day. Recommend a departure, including its fare and boarding location, and explain which of the three destinations is quickest to reach.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_any, contains_duration, contains_phrase, contains_time,
                        final_answer, navigated_journeys, navigated_to_path, run_verifier)

TASK_ID = "Megabus--6"
PHL_ID = 127
BAL_ID, WDC_ID = 143, 142
TOP3 = [("Baltimore", 15.99, 105), ("New York", 19.99, 110), ("Washington", 31.98, 205)]
MORNING_DEP = "07:00"
MORNING_FARE = 15.99
BOARDING_KEY = "Filbert"
WDC_1003_CHEAPEST = 31.98


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_fare_finder", navigated_to_path(traj, "/fare-finder"),
                "required_path=/fare-finder")
    judge.check("visited_fare_finder_search",
                any("/fare-finder/search" in u and "originId=127" in u
                    for u in [str(s.get("url", "")) for s in traj.get("steps") or [] if isinstance(s, dict)]),
                "required: /fare-finder/search?originId=127 (Philadelphia)")
    for name, fare, _ in TOP3:
        judge.check(f"answer_lists_{name.lower().replace(' ', '_')}",
                    contains_phrase(answer, name) and contains_amount(answer, fare),
                    f"expected {name} with its starting fare ${fare}")
    judge.check("answer_fastest_is_baltimore", contains_phrase(answer, "Baltimore"),
                "Baltimore (1h45m) is the fastest of the three")
    judge.check("answer_fastest_duration", contains_duration(answer, 105),
                "expected the Baltimore trip time 1h45m (105 min)")
    # journey planner checks for the cheapest destination (Baltimore) on 10-03
    judge.check("visited_phl_bal_1003_results",
                navigated_journeys(traj, PHL_ID, BAL_ID, "2026-10-03"),
                "required: journeys PHL->Baltimore on 2026-10-03")
    judge.check("answer_morning_departure", contains_time(answer, MORNING_DEP),
                f"expected the cheapest morning departure {MORNING_DEP} (7:00am)")
    judge.check("answer_morning_fare", contains_amount(answer, MORNING_FARE),
                f"expected the morning departure fare ${MORNING_FARE}")
    judge.check("answer_boarding_stop", contains_phrase(answer, BOARDING_KEY),
                "expected the Philadelphia boarding stop 1001 Filbert Street")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
