#!/usr/bin/env python3
"""Verify Instructure--17."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--17"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_support_faq", "/support/canvas-support-faq")
    # Frozen ground truth (seed DB, faq_items "What are the limitations?" and
    # "Can I use it even though I'm not a teacher?"): the limitation is that Free
    # Canvas Accounts don't contain all the features available to institutional users;
    # non-teachers CAN use it (students, parents, anyone who wants to use Canvas
    # learning tools can sign up).
    judge.check("answer_limitation",
                contains_all(answer, ["contain all the features", "institutional users"]),
                "expected the limitation: free accounts do not contain all the features "
                "available to institutional users of Canvas")
    judge.check("answer_non_teachers_can_use",
                contains_any(answer, ["yes", "can sign up", "anyone else"]),
                "expected that non-teachers can use it")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
