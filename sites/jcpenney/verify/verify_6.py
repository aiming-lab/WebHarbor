#!/usr/bin/env python3
"""Verify JCPenney--6."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--6"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_kayley_product",
                       "/p/pop-womens-kayley-flat-heel-slouch-boots/ppr5008672777")
    check_visited_path(judge, traj, "visited_bag", "/cart")
    # Frozen ground truth (seed DB, ppid ppr5008672777 @ $63.00): bag subtotal $63,
    # shipping $8.95 (subtotal < $75), estimated tax $5.20 (8.25%).
    judge.check("answer_subtotal", contains_amount(answer, 63),
                "expected the bag subtotal $63.00")
    judge.check("answer_shipping", contains_amount(answer, 8.95),
                "expected the shipping charge $8.95")
    judge.check("answer_tax", contains_amount(answer, 5.20),
                "expected the estimated tax $5.20")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
