#!/usr/bin/env python3
"""Verify Instructure--9."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_careers", "/about/careers")
    # Frozen ground truth (seed DB, jobs slug builder-instructure-foundry-N): comp
    # "$150K - $230K", employment_type "FullTime", location "US-REMOTE". The employment
    # type is not printed on the job row; it is proven by applying the Employment Type
    # filter (FullTime) and seeing the role remain.
    judge.check("answer_salary_range",
                contains_klabel(answer, "$150K") and contains_klabel(answer, "$230K"),
                "expected the salary range $150K - $230K")
    judge.check("answer_employment_type",
                contains_any(answer, ["FullTime", "Full Time", "Full-Time", "full time"]),
                "expected the employment type FullTime")
    judge.check("answer_location", contains_phrase(answer, "US-REMOTE"),
                "expected the location US-REMOTE")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
