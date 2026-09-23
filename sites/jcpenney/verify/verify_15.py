#!/usr/bin/env python3
"""Verify JCPenney--15."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--15"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_coupons_page", "/m/jcpenney-coupons")
    # Frozen ground truth (seed DB): GOSHOP15 — "$10 off your $50 purchase",
    # minimum purchase $50, exclusions "Excludes gift cards." (valid through Oct. 15, 2026).
    judge.check("answer_code", contains_phrase(answer, "GOSHOP15"),
                "expected the coupon code GOSHOP15")
    judge.check("answer_discount", contains_all(answer, ["$10 off", "$50"]),
                "expected the $10 off your $50 purchase discount")
    judge.check("answer_minimum", contains_all(answer, ["minimum purchase", "50"]),
                "expected the $50 minimum purchase")
    judge.check("answer_exclusions", contains_phrase(answer, "Excludes gift cards"),
                "expected the exact exclusions wording 'Excludes gift cards.'")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
