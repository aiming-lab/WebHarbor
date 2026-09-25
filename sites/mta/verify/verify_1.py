#!/usr/bin/env python3
"""Verify MTA--1.

Late concert at Madison Square Garden on a weeknight: last weekday train from
Penn Station toward Ronkonkoma, its arrival; if missed, the first morning
train from NYC the next day; the one-way off-peak fare.

Frozen ground truth (seed DB): Ronkonkoma Branch weekday, direction 0 (to
Ronkonkoma): last departure from Penn Station (stop 237) = 23:55, arrives
Ronkonkoma (179) 01:20. First morning departure the next weekday = 05:16
(arrives 06:39). One-Way Off-Peak Ronkonkoma (zone 10) -> Penn Station
(zone 1) = $16.00.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_time, final_answer,
                        navigated_fare_finder, navigated_timetable, run_verifier)

TASK_ID = "MTA--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_ronkonkoma_timetable",
                navigated_timetable(traj, "/schedules/lirr/ronkonkoma"),
                "required: /schedules/lirr/ronkonkoma")
    judge.check("visited_fare_finder_ronkonkoma_offpeak",
                navigated_fare_finder(traj, "Ronkonkoma", "Penn Station", "One-Way Off-Peak"),
                "required: fare finder from=Ronkonkoma to=Penn Station ticket=One-Way Off-Peak")
    judge.check("answer_last_train_1155pm", contains_time(answer, "23:55") or contains_time(answer, "11:55", "p"),
                "last weekday train departs 11:55 p.m. (23:55)")
    judge.check("answer_arrival_120am", contains_time(answer, "01:20") or contains_time(answer, "1:20", "a"),
                "arrives Ronkonkoma 1:20 a.m.")
    judge.check("answer_first_morning_516", contains_time(answer, "05:16") or contains_time(answer, "5:16", "a"),
                "first morning train departs 5:16 a.m.")
    judge.check("answer_fare_16_00", contains_amount(answer, 16.00),
                "one-way off-peak fare $16.00")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
