#!/usr/bin/env python3
"""Verify MacysWineShop--13: guest cart: 3 bottles of Time & Tide Chardonnay"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--13"

TIMETIDE_VARIANT_ID = 2


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_timetide_page",
                       "/products/2023-time-tide-chardonnay-monterey-county")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # Frozen ground truth: subtotal $56.97, shipping $14.95, processing $2.95,
    # total $74.87, progress message "Add 3 bottles for free shipping!".
    judge.check("answer_subtotal", contains_money(answer, 56.97),
                "expected cart subtotal $56.97")
    judge.check("answer_shipping", contains_money(answer, 14.95),
                "expected shipping $14.95")
    judge.check("answer_processing", contains_money(answer, 2.95),
                "expected processing fee $2.95")
    judge.check("answer_total", contains_money(answer, 74.87),
                "expected cart total $74.87")
    judge.check("answer_free_shipping_progress",
                contains_phrase(answer, "free shipping") and contains_count(answer, 3),
                "expected the free-shipping progress message: add 3 bottles")
    # DB after-state: exactly one guest cart row — 3 x Time & Tide Chardonnay.
    delta = table_delta(initial_db, after_db, "cart_items")
    from verify_lib import row_dict, table_columns
    cols = table_columns(after_db, "cart_items")
    added_rows = [dict(zip(cols, row)) for row in delta["added"]]
    ok = (len(added_rows) == 1 and len(delta["removed"]) == 0 and len(delta["changed"]) == 0
          and added_rows[0]["variant_id"] == TIMETIDE_VARIANT_ID
          and added_rows[0]["user_id"] is None and added_rows[0]["quantity"] == 3)
    judge.check("db_guest_cart_row", ok,
                f"expected exactly one added guest cart row (variant {TIMETIDE_VARIANT_ID}, qty 3); "
                f"delta={ {k: len(v) for k, v in delta.items()} }")
    check_only_tables_changed(judge, initial_db, after_db, {"cart_items"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
