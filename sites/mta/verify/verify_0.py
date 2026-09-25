#!/usr/bin/env python3
"""Verify MTA--0.

Father commutes weekdays from Valley Stream (LIRR Long Beach Branch) to Penn
Station and must arrive by 9:15 a.m. Find the latest weekday train boarding at
Valley Stream that still arrives in time, the ride time, the one-way peak
fare, and whether any planned service changes this weekend affect a Saturday
trip on his branch.

Frozen ground truth (seed DB): Long Beach Branch weekday, direction 1 (to
Penn Station/Grand Central/Atlantic Terminal): departures from Valley
Stream (stop 211) arriving Penn (237) by 9:15 a.m. — the latest is the 8:20
a.m. departure (arrives 8:59 a.m., 39-minute ride); the next train departs
8:45 and arrives 9:16 (one minute late). One-Way Peak fare Valley Stream
(zone 4) -> Penn Station (zone 1) = $13.50. The weekend planned-changes
window (Sep 25 17:00 - Sep 28 02:00) contains NO Long Beach Branch entries
(West Hempstead Branch is suspended instead).
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, contains_time,
                        final_answer, navigated_fare_finder, navigated_planned_changes,
                        navigated_timetable, run_verifier)

TASK_ID = "MTA--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    # navigation gates: Long Beach Branch weekday timetable toward Manhattan,
    # fare finder for the exact pair + ticket, weekend LIRR planned changes
    judge.check("visited_long_beach_timetable",
                navigated_timetable(traj, "/schedules/lirr/long-beach"),
                "required: /schedules/lirr/long-beach")
    judge.check("visited_fare_finder_valley_stream_peak",
                navigated_fare_finder(traj, "Valley Stream", "Penn Station", "One-Way Peak"),
                "required: fare finder from=Valley Stream to=Penn Station ticket=One-Way Peak")
    judge.check("visited_lirr_weekend_changes",
                navigated_planned_changes(traj, "lirr", "weekend"),
                "required: /planned-service-changes?mode=lirr&when=weekend")
    # answer gates
    judge.check("answer_departure_820", contains_time(answer, "8:20"),
                "latest qualifying departure is 8:20 a.m.")
    judge.check("answer_arrival_859", contains_time(answer, "8:59"),
                "arrival 8:59 a.m.")
    judge.check("answer_ride_39_min", contains_phrase(answer, "39 min") or contains_phrase(answer, "39-minute"),
                "ride time is 39 minutes")
    judge.check("answer_fare_13_50", contains_amount(answer, 13.50),
                "one-way peak fare $13.50")
    judge.check("answer_no_long_beach_changes",
                contains_phrase(answer, "no planned") or contains_phrase(answer, "none")
                or contains_phrase(answer, "no service changes") or contains_phrase(answer, "not affected")
                or contains_phrase(answer, "no changes"),
                "weekend: no planned changes affect the Long Beach Branch")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
