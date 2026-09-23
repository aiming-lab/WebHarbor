#!/usr/bin/env python3
"""Verify Instructure--19."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_account", "/account")
    # Frozen ground truth (seed DB): bob_c has exactly one webinar registration,
    # "Design Matters: Key Lessons for Better Canvas Courses".
    judge.check("answer_webinar_title",
                contains_all(answer, ["Design Matters", "Better Canvas Courses"]),
                "expected the registered webinar 'Design Matters: Key Lessons for Better "
                "Canvas Courses'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
