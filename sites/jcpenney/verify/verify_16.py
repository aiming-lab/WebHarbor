#!/usr/bin/env python3
"""Verify JCPenney--16."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--16"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_gift_cards", "/gift-cards")
    # Frozen ground truth (app.py deterministic demo balance: 0.<last two digits> * 100
    # for card 6249881234570021 -> $21.00, stable across repeated checks).
    judge.check("answer_balance", contains_amount(answer, 21.00),
                "expected the gift card balance $21.00")
    judge.check("answer_balance_stable", "unchanged" in answer or contains_phrase(answer, "still $21"),
                "expected the answer to confirm the balance is unchanged on the second check")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
