#!/usr/bin/env python3
"""Verify Instructure--10."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_careers", "/about/careers")
    # Frozen ground truth (seed DB, jobs): the only customer success role located in
    # Mexico is "Associate Customer Success Manager - Higher Education"
    # (department Customer Success, comp "MX$427K - MX$532K ...").
    judge.check("answer_role_title",
                contains_phrase(answer, "Associate Customer Success Manager"),
                "expected the role 'Associate Customer Success Manager - Higher Education'")
    judge.check("answer_department", contains_phrase(answer, "Customer Success"),
                "expected the department Customer Success")
    judge.check("answer_comp_range",
                contains_klabel(answer, "$427K") and contains_klabel(answer, "$532K"),
                "expected the MX$427K - MX$532K compensation range")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
