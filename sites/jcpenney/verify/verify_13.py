#!/usr/bin/env python3
"""Verify JCPenney--13."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_rewards", "/account/dashboard/rewards")
    # Frozen ground truth (seed DB, david): 310 reward points, tier Member,
    # most recent activity: Purchase at jcp.com, 210 pts, September 7, 2026.
    judge.check("answer_points_balance", contains_count(answer, 310),
                "expected the 310-point balance")
    judge.check("answer_tier", contains_phrase(answer, "Member"),
                "expected the membership tier Member")
    judge.check("answer_recent_description", contains_phrase(answer, "Purchase at jcp.com"),
                "expected the most recent activity description")
    judge.check("answer_recent_points", contains_count(answer, 210),
                "expected the most recent activity points 210")
    judge.check("answer_recent_date", contains_date_phrase(answer, "September 7, 2026"),
                "expected the most recent activity date September 7, 2026")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
