#!/usr/bin/env python3
"""Verify JCPenney--10."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_order_tracker", "/orders")
    # Frozen ground truth (seed DB): order JCP2609021005 ships to ZIP 94110 —
    # status In Transit, carrier USPS, items: St. John's Bay Mens Long Sleeve Classic
    # Fit Flannel Shirt ($20.99) + Linery Cotton Quick-Dry Loop Textured 12 Pc
    # Washcloths ($19.59).
    judge.check("answer_status", contains_phrase(answer, "In Transit"),
                "expected the order status In Transit")
    judge.check("answer_carrier", contains_phrase(answer, "USPS"),
                "expected the carrier USPS")
    judge.check("answer_item_flannel", contains_all(answer, ["Flannel Shirt", "20.99"]),
                "expected the St. John's Bay flannel shirt item")
    judge.check("answer_item_washcloths", contains_all(answer, ["Washcloths", "19.59"]),
                "expected the Linery 12 Pc Washcloths item")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
