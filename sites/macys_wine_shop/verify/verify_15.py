#!/usr/bin/env python3
"""Verify MacysWineShop--15: alice checkout: default address + card, age confirm"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--15"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # Frozen ground truth: order number MWS1050, ship-to San Francisco, CA, total $109.38.
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_ship_city", contains_phrase(answer, "San Francisco"),
                "expected the shipping city San Francisco")
    judge.check("answer_ship_state", contains_phrase(answer, "CA"),
                "expected the shipping state CA")
    judge.check("answer_order_total", contains_money(answer, 109.38),
                "expected the order total $109.38")
    # DB after-state: one new order + its two items, alice's cart rows consumed.
    from verify_lib import table_columns
    cols = table_columns(after_db, "orders")
    orders_added = [dict(zip(cols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] == 1
                 and abs(orders_added[0]["total"] - 109.38) < 0.005)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added order row MWS1050 (alice, total 109.38)")
    items = table_delta(initial_db, after_db, "order_items")
    ok_items = len(items["added"]) == 2 and len(items["removed"]) == 0
    judge.check("db_new_order_items", ok_items,
                f"expected two added order_items rows; delta={ {k: len(v) for k, v in items.items()} }")
    cart = table_delta(initial_db, after_db, "cart_items")
    ok_cart = len(cart["removed"]) == 2 and len(cart["added"]) == 0 and len(cart["changed"]) == 0
    judge.check("db_alice_cart_consumed", ok_cart,
                "expected alice's two seeded cart rows removed on order placement")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items", "cart_items"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
