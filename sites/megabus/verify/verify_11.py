#!/usr/bin/env python3
"""Verify Megabus--11.

Compare Oct 3 morning departures to Washington from New York, Philadelphia AND
Baltimore: which city has the earliest first departure after 6:00am, what does
that ticket cost per traveler, how long does that journey take, and how many
services run from each city that day?

Frozen ground truth (seed DB): NY->WDC 10-03 first after 06:00 = 06:30 ->
13:40 @ $39.99 (7h10m / 430 min), 13 services; PHL->WDC 10-03 first after
06:00 = 07:00 -> 10:40 @ $31.98 (3h40m / 220 min), 5 services; BAL->WDC
10-03 first after 06:00 = 06:50 -> 08:15 @ $19.99 (1h25m / 85 min), 24
services. New York has the earliest first departure (06:30).
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_duration, contains_phrase, contains_time,
                        final_answer, navigated_journeys, run_verifier)

TASK_ID = "Megabus--11"
NY_ID, PHL_ID, BAL_ID, WDC_ID = 123, 127, 143, 142
DATE = "2026-10-03"
NY_FIRST = ("06:30", 39.99, 430)
COUNTS = {"New York": 13, "Philadelphia": 5, "Baltimore": 24}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_ny_results",
                navigated_journeys(traj, NY_ID, WDC_ID, DATE),
                f"required: journeys NY->WDC on {DATE}")
    judge.check("visited_phl_results",
                navigated_journeys(traj, PHL_ID, WDC_ID, DATE),
                f"required: journeys PHL->WDC on {DATE}")
    judge.check("visited_bal_results",
                navigated_journeys(traj, BAL_ID, WDC_ID, DATE),
                f"required: journeys BAL->WDC on {DATE}")
    judge.check("answer_new_york_earliest", contains_phrase(answer, "New York")
                and (contains_phrase(answer, "earliest") or contains_phrase(answer, "earlier")),
                "New York has the earliest first departure after 6am (06:30)")
    judge.check("answer_ny_departure_time", contains_time(answer, NY_FIRST[0]),
                f"expected the NY first departure {NY_FIRST[0]}")
    judge.check("answer_ny_fare", contains_amount(answer, NY_FIRST[1]),
                f"expected the NY ticket ${NY_FIRST[1]} per traveler")
    judge.check("answer_ny_duration", contains_duration(answer, NY_FIRST[2]),
                "expected the NY journey duration 7h10m")
    for city, count in COUNTS.items():
        judge.check(f"answer_{city.lower().replace(' ', '_')}_count",
                    contains_count(answer, count),
                    f"expected {count} services from {city} that day")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
