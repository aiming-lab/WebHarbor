#!/usr/bin/env python3
"""Verify MacysWineShop--20: bob's most recent order"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--20"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_orders_page", "/account/orders")
    check_visited_path(judge, traj, "visited_order_detail", "/account/orders/MWS1044")
    # Frozen ground truth: MWS1044, Shipped, total $79.40, contains the
    # Golden State Essentials Case (placed September 14, 2026).
    judge.check("answer_order_number", contains_phrase(answer, "MWS1044"),
                "expected the most recent order MWS1044")
    judge.check("answer_status", contains_phrase(answer, "Shipped"),
                "expected the status Shipped")
    judge.check("answer_total", contains_money(answer, 79.40),
                "expected the order total $79.40")
    judge.check("answer_wine", contains_phrase(answer, "Golden State Essentials Case"),
                "expected the order's wine: Golden State Essentials Case")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
