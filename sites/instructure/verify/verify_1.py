#!/usr/bin/env python3
"""Verify Instructure--1."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--1"


MADISON_PATH = "/resources/case-studies/staying-course-better-benchmarks-madison-county"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_madison_case_study", MADISON_PATH)
    # Frozen ground truth (seed DB, resources slug
    # staying-course-better-benchmarks-madison-county): stat bar
    # "12,700 students"; body "every one of Madison County's 11 elementary schools earned
    # an A rating from the state" (Mississippi per the stat bar and the milestones block).
    judge.check("answer_student_count", contains_count(answer, 12700),
                "expected 12,700 students served by the district")
    judge.check("answer_elementary_schools", contains_count(answer, 11),
                "expected the 11 elementary schools")
    judge.check("answer_rating", contains_all(answer, ["A rating", "Mississippi"]),
                "expected an A rating from the state of Mississippi")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
