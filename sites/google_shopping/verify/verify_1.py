#!/usr/bin/env python3
"""Verify the Departments page report in Google Shopping--1."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Google Shopping--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the task names the Departments page reached from the Search tab.
    check_visited_path(judge, traj, "visited_departments_page", "/departments")
    # Frozen ground truth (seed DB, departments table): 15 departments, first tile 'Apparel'.
    judge.check("answer_department_count", contains_count(answer, 15), "expected 15 departments")
    judge.check("answer_first_department", contains_phrase(answer, "Apparel"),
                "expected the first tile 'Apparel'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
