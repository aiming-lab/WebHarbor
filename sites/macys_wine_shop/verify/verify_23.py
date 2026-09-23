#!/usr/bin/env python3
"""Verify MacysWineShop--23: carol password change + revert"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--23"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_password_page", "/account/password")
    inputs = input_texts(traj)
    judge.check("entered_new_password",
                any("AutumnCellar77!" in v for v in inputs),
                f"expected AutumnCellar77! in an input step; observed={inputs!r}")
    judge.check("reverted_to_original_password",
                sum(1 for v in inputs if "TestPass123!" in v) >= 1,
                "expected the original password TestPass123! to be re-entered")
    # Frozen ground truth: the account page confirms each change with
    # "Password changed successfully."
    judge.check("answer_change_confirmed",
                contains_phrase(answer, "Password changed successfully"),
                "expected the account page confirmation 'Password changed successfully.'")
    # DB after-state: the revert restores the seed row exactly.
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
