#!/usr/bin/env python3
"""Verify JCPenney--18."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--18"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_store_2011", "/stores/2011")
    # Frozen ground truth (seed DB, store #2011): 18601 33rd Ave W, Lynnwood WA 98037;
    # Sunday hours 11:00-19:00; services: Curbside Pick up.
    judge.check("answer_street_address", contains_all(answer, ["18601 33rd Ave W", "Lynnwood"]),
                "expected the full street address 18601 33rd Ave W, Lynnwood")
    judge.check("answer_sunday_hours", contains_phrase(answer, "11:00-19:00"),
                "expected the Sunday hours 11:00-19:00")
    judge.check("answer_sunday_day", contains_any(answer, ["Sun", "Sunday"]),
                "expected the day named (Sun/Sunday)")
    judge.check("answer_services", contains_phrase(answer, "Curbside Pick up"),
                "expected the Curbside Pick up service")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
