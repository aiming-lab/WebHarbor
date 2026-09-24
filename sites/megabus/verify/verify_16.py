#!/usr/bin/env python3
"""Verify Megabus--16.

Log in as Alice Johnson; list her upcoming trips (routes, dates, departure
times, totals); for the two-traveler trip report the per-traveler fare shown
on the departure schedule for that route and date; open the AEG7CWY booking
under Change trip to confirm its total; check the tracker: is her 5:30am
departure currently on time? State which booking has the larger total.

Frozen ground truth (seed DB): alice has two confirmed upcoming trips —
AEG7CWY: Philadelphia, PA -> New York, NY, 2026-10-03, 05:30 -> 07:30, 2
travelers, total $56.22 (booking_journeys price 51.98 -> per-traveler fare
$25.99, shown on the PHL->NY 2026-10-03 schedule card); K4N2WZ: New York, NY
-> Washington, DC, 2026-10-03, 09:30 -> 14:20, 1 traveler, total $43.98.
AEG7CWY has the larger total. The tracker shows the 05:30 PHL->NY departure
On time (no tracked delay for that journey).
"""
from verify_lib import (check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase,
                        contains_time, final_answer, navigated_journeys, navigated_to,
                        run_verifier)

TASK_ID = "Megabus--16"
PHL_ID, NY_ID = 127, 123
TRIPS = {"AEG7CWY": ("Philadelphia", "New York", "05:30", 56.22, 2, 25.99),
         "K4N2WZ": ("New York", "Washington", "09:30", 43.98, 1, 39.99)}
PER_TRAVELER = 25.99


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_account", "/account-management")
    judge.check("visited_schedule_results",
                navigated_journeys(traj, PHL_ID, NY_ID, "2026-10-03"),
                "required: journeys PHL->NY on 2026-10-03 (per-traveler fare)")
    judge.check("opened_booking_change_trip",
                navigated_to(traj, "ref=AEG7CWY"),
                "required: the AEG7CWY booking opened under Change trip")
    check_visited_path(judge, traj, "visited_tracker", "/journey-planner/track")
    for ref, (origin, dest, dep, total, pax, per_pax) in TRIPS.items():
        judge.check(f"answer_lists_{ref.lower()}",
                    contains_phrase(answer, origin) and contains_phrase(answer, dest)
                    and contains_time(answer, dep) and contains_amount(answer, total),
                    f"expected {ref}: {origin}->{dest} {dep} total ${total}")
    judge.check("answer_per_traveler_fare", contains_amount(answer, PER_TRAVELER),
                f"expected the per-traveler fare ${PER_TRAVELER} for the 2-traveler trip (AEG7CWY)")
    judge.check("answer_confirms_booking_total",
                contains_amount(answer, 56.22) and contains_phrase(answer, "56.22"),
                "expected the AEG7CWY total $56.22 confirmed on the booking page")
    judge.check("answer_tracker_on_time",
                contains_time(answer, "05:30") and contains_phrase(answer, "on time"),
                "the 5:30am departure is On time on the tracker")
    judge.check("answer_larger_total",
                contains_phrase(answer, "AEG7CWY")
                and (contains_phrase(answer, "larger") or contains_phrase(answer, "bigger")
                     or contains_phrase(answer, "greater")),
                "AEG7CWY ($56.22) has the larger total")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
