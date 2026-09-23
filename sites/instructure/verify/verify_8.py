#!/usr/bin/env python3
"""Verify Instructure--8."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the careers board (the Department filter is client-side and does
    # not change the URL, so the board page itself is the required surface).
    check_visited_path(judge, traj, "visited_careers", "/about/careers")
    # Frozen ground truth (seed DB): 6 jobs with department Engineering; list order 11
    # (the first engineering row) is "Director, AI Center of Excellence".
    judge.check("answer_engineering_count", contains_count(answer, 6),
                "expected 6 engineering positions")
    judge.check("answer_first_role", contains_phrase(answer, "Director, AI Center of Excellence"),
                "expected the first role 'Director, AI Center of Excellence'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
