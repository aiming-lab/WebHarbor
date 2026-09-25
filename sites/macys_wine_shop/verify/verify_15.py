#!/usr/bin/env python3
"""Verify MacysWineShop--15 (KEEP): register + order the Closed Window Pinot Noir.

Adapted unchanged in substance from the depth review's KEEP contract for the
old --24 (32 measured steps): the trajectory registers a brand-new account,
adds 3 bottles of the 2023 Closed Window Pinot Noir Willamette Valley
($19.99, enough for the 3-bottle checkout minimum), places the order with its
own details, and reaches the confirmation. Frozen ground truth: the new order
is MWS1050 (guest-free path: registered user) with subtotal $59.97, shipping
$14.95, processing $2.95, total $77.87.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money, contains_phrase, final_answer,
                        navigated_to, run_verifier, table_delta, table_columns)

TASK_ID = "MacysWineShop--15"

CLOSED_WINDOW_HANDLE = "2023-closed-window-pinot-noir-willamette-valley"
TOTAL = 77.87


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
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the reported total ${TOTAL:.2f} (3 x $19.99 + $14.95 + $2.95)")
    # DB after-state: one new user, one new order (MWS1050) holding the Closed
    # Window Pinot Noir with >= 3 bottles (the site's checkout minimum), and
    # the reported total equals the DB order total.
    users = table_delta(initial_db, after_db, "users")
    ok_users = len(users["added"]) == 1 and len(users["removed"]) == 0
    judge.check("db_new_user_row", ok_users,
                f"expected exactly one added user row; delta={ {k: len(v) for k, v in users.items()} }")
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added order row MWS1050 (total 77.87)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    target = [row for row in items_added if row["product_handle"] == CLOSED_WINDOW_HANDLE]
    ok_items = (len(items_added) >= 1 and len(target) == 1 and target[0]["quantity"] >= 3)
    judge.check("db_order_item_closed_window", ok_items,
                "expected one added order_items row for the Closed Window Pinot Noir with qty >= 3")
    if orders_added:
        total = orders_added[0]["total"]
        judge.check("answer_total_matches_db", contains_money(answer, total),
                    f"expected the reported total to equal the DB order total ${total:.2f}")
    check_only_tables_changed(judge, initial_db, after_db,
                              {"users", "orders", "order_items", "cart_items"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
