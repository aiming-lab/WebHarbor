#!/usr/bin/env python3
"""Verify Instructure--5."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--5"


MADISON_PATH = "/resources/case-studies/staying-course-better-benchmarks-madison-county"
KERSHAW_PATH = "/resources/case-studies/kershaw-county-mastery-case-study"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: BOTH case studies must be opened (the comparison is the task).
    check_visited_path(judge, traj, "visited_madison_case_study", MADISON_PATH)
    check_visited_path(judge, traj, "visited_kershaw_case_study", KERSHAW_PATH)
    # Frozen ground truth (seed DB stat bars): Madison County 12,700 students;
    # Kershaw County 11,000 students; difference 1,700.
    judge.check("answer_madison_count", contains_count(answer, 12700),
                "expected Madison County's 12,700 students")
    judge.check("answer_kershaw_count", contains_count(answer, 11000),
                "expected Kershaw County's 11,000 students")
    judge.check("answer_more_students",
                contains_any(answer, ["Madison"]) and contains_count(answer, 1700),
                "expected Madison County serving more students by about 1,700")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
