#!/usr/bin/env python3
"""Verify Instructure--4."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--4"


EDISON_PATH = "/resources/case-studies/edison-high-school-case-study"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_edison_case_study", EDISON_PATH)
    # Frozen ground truth (seed DB, resources slug edison-high-school-case-study, stat
    # bar): Location: New Jersey / Students: 2,000 / Adopted Parchment: 2024.
    judge.check("answer_state", contains_phrase(answer, "New Jersey"),
                "expected the state New Jersey")
    judge.check("answer_student_count", contains_count(answer, 2000),
                "expected 2,000 students")
    judge.check("answer_product_and_year",
                contains_phrase(answer, "Parchment") and contains_count(answer, 2024),
                "expected Parchment adopted in 2024")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
