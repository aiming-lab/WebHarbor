#!/usr/bin/env python3
"""Verify JCPenney--28."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--28"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_order_history", "/account/dashboard/orders")
    check_visited_path(judge, traj, "visited_order_detail", "/orders/JCP2609190003")
    # Frozen ground truth (seed DB): the wrong-password flash reads "The email or
    # password you entered is incorrect. Please try again."; alice's order still in
    # flight is JCP2609190003 — status Shipped, UPS, tracking 1Z5R892W0402311887.
    judge.check("answer_wrong_password_error",
                contains_phrase(answer, "email or password you entered is incorrect"),
                "expected the exact sign-in error message")
    judge.check("answer_order_number", contains_phrase(answer, "JCP2609190003"),
                "expected order number JCP2609190003")
    judge.check("answer_order_status", contains_phrase(answer, "Shipped"),
                "expected the order status Shipped")
    judge.check("answer_tracking", contains_phrase(answer, "1Z5R892W0402311887"),
                "expected tracking number 1Z5R892W0402311887")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
