#!/usr/bin/env python3
"""Verify JCPenney--9."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_order_history", "/account/dashboard/orders")
    check_visited_path(judge, traj, "visited_order_detail", "/orders/JCP2609131004")
    # Frozen ground truth (seed DB): bob's most recent order JCP2609131004
    # (placed 2026-09-13), Delivered, USPS, tracking 9400111899560008213442,
    # one item: St. John's Bay Womens Mid Rise Bootcut Jean at $23.09.
    judge.check("answer_order_number", contains_phrase(answer, "JCP2609131004"),
                "expected order number JCP2609131004")
    judge.check("answer_status", contains_phrase(answer, "Delivered"),
                "expected the order status Delivered")
    judge.check("answer_carrier", contains_phrase(answer, "USPS"),
                "expected the shipping carrier USPS")
    judge.check("answer_tracking", contains_phrase(answer, "9400111899560008213442"),
                "expected tracking number 9400111899560008213442")
    judge.check("answer_item", contains_all(answer, ["Mid Rise Bootcut Jean", "23.09"]),
                "expected the St. John's Bay Womens Mid Rise Bootcut Jean at $23.09")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
