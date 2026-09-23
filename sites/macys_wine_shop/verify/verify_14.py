#!/usr/bin/env python3
"""Verify MacysWineShop--14: alice's seeded cart"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--14"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # Frozen ground truth (seed cart): 2 x 2021 Free Flight Pinot Noir ($29.98 line)
    # + 1 x Golden State Essentials Case ($76.45 line) = 8 bottles, FREE shipping,
    # order total $109.38.
    judge.check("answer_item_pinot",
                contains_phrase(answer, "Free Flight Pinot Noir") and contains_money(answer, 29.98),
                "expected the 2021 Free Flight Pinot Noir x2 line at $29.98")
    judge.check("answer_item_case",
                contains_phrase(answer, "Golden State Essentials Case") and contains_money(answer, 76.45),
                "expected the Golden State Essentials Case x1 line at $76.45")
    judge.check("answer_bottle_count", contains_count(answer, 8),
                "expected 8 bottles in the cart")
    judge.check("answer_shipping_free", contains_free(answer),
                "expected FREE shipping (8 bottles >= 6)")
    judge.check("answer_order_total", contains_money(answer, 109.38),
                "expected the order total $109.38")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
