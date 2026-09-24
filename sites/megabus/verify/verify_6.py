#!/usr/bin/env python3
"""Verify Megabus--6.

Use the fare finder to list the three cheapest destinations reachable from
Philadelphia with their starting fares; which of those three is fastest to
reach and how long does that trip take? Then use the journey planner to check
October 3rd departures to the cheapest destination: report the cheapest
morning departure, its fare, and where it boards in Philadelphia. Finally,
does the fare finder's starting fare for Washington match that route's
cheapest October 3rd fare?

Frozen ground truth (seed DB): fare-finder origin Philadelphia, PA (id 127):
1) Baltimore, MD from $15.99 (fastest 1h45m / 105 min); 2) New York, NY from
$19.99 (fastest 1h50m / 110 min); 3) Washington, DC from $31.98 (fastest
3h25m / 205 min). Baltimore is the fastest of the three at 1h45m. PHL->BAL
2026-10-03 cheapest morning (06:00-11:59) departure = 07:00 @ $15.99, boarding
at the Peter Pan Bus Lines / Trailways bus stop at Philadelphia - 1001
Filbert Street. PHL->WDC 2026-10-03 cheapest fare = $31.98, which MATCHES
the fare finder's starting fare for Washington.
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
    # Washington starting-fare vs 10-03 cheapest comparison
    judge.check("visited_phl_wdc_1003_results",
                navigated_journeys(traj, PHL_ID, WDC_ID, "2026-10-03"),
                "required: journeys PHL->Washington on 2026-10-03")
    judge.check("answer_wdc_fares_match",
                contains_amount(answer, WDC_1003_CHEAPEST)
                and (contains_any(answer, ["match", "same", "identical", "equal", "yes"])),
                "expected: the fare finder's Washington starting fare $31.98 matches the "
                "cheapest October 3rd fare $31.98")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
