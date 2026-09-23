#!/usr/bin/env python3
"""Verify MacysWineShop--24: register + order the Closed Window Pinot Noir"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--24"

CLOSED_WINDOW_HANDLE = "2023-closed-window-pinot-noir-willamette-valley"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_register_page", "/register")
    check_visited_path(judge, traj, "visited_closed_window_page", "/products/" + CLOSED_WINDOW_HANDLE)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for the new order MWS1050")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    # DB after-state: one new user, one new order (MWS1050) holding the Closed
    # Window Pinot Noir with >= 3 bottles (the site's checkout minimum), and the
    # reported total equals the DB order total.
    users = table_delta(initial_db, after_db, "users")
    ok_users = len(users["added"]) == 1 and len(users["removed"]) == 0
    judge.check("db_new_user_row", ok_users,
                f"expected exactly one added user row; delta={ {k: len(v) for k, v in users.items()} }")
    from verify_lib import table_columns
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050")
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added order row MWS1050")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    target = [row for row in items_added if row["product_handle"] == CLOSED_WINDOW_HANDLE]
    ok_items = (len(items_added) >= 1 and len(target) == 1 and target[0]["quantity"] >= 3)
    judge.check("db_order_item_closed_window", ok_items,
                f"expected one added order_items row for the Closed Window Pinot Noir with qty >= 3")
    if orders_added:
        total = orders_added[0]["total"]
        judge.check("answer_total_matches_db", contains_money(answer, total),
                    f"expected the reported total to equal the DB order total ${total:.2f}")
    check_only_tables_changed(judge, initial_db, after_db,
                             {"users", "orders", "order_items", "cart_items"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
