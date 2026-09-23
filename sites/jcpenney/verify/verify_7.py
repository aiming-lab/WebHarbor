#!/usr/bin/env python3
"""Verify JCPenney--7."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_bag", "/cart")
    # Frozen ground truth (seed DB, alice's bag): Arizona Mens Hooded ... Twofer
    # Flannel Shirt ($31.49, qty 1) + PUMA Sweatpants ... Jogger Pant ($37.50, qty 1);
    # subtotal $68.99, estimated tax $5.69.
    judge.check("answer_item_one", contains_all(answer, ["Arizona", "flannel shirt"]),
                "expected the Arizona twofer flannel shirt in the bag report")
    judge.check("answer_item_one_qty_price", contains_all(answer, ["1", "31.49"]),
                "expected Arizona flannel qty 1 at $31.49")
    judge.check("answer_item_two", contains_all(answer, ["PUMA", "jogger pant"]),
                "expected the PUMA jogger pant in the bag report")
    judge.check("answer_item_two_qty_price", contains_amount(answer, 37.50),
                "expected the PUMA jogger qty 1 at $37.50 (the currency filter renders two decimals)")
    judge.check("answer_subtotal", contains_amount(answer, 68.99),
                "expected the bag subtotal $68.99")
    judge.check("answer_tax", contains_amount(answer, 5.69),
                "expected the estimated tax $5.69")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
