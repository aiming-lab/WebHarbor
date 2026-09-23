#!/usr/bin/env python3
"""Verify MacysWineShop--1: guest direct purchase of the Time & Tide Chardonnay.

Frozen ground truth (seed): the 2023 Time & Tide Chardonnay Monterey County
costs $18.99; 3 bottles subtotal to $56.97, shipping stays $14.95 (3 bottles
are under the 6-bottle free-shipping rule), processing $2.95, total $74.87;
the placed guest order is MWS1050.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money, contains_phrase, final_answer,
                        navigated_search_with, navigated_to, run_verifier, table_delta,
                        table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--1"
HANDLE = "2023-time-tide-chardonnay-monterey-county"
TOTAL = 74.87
GROUND_TRUTH = ("3 bottles of the 2023 Time & Tide Chardonnay Monterey County at $18.99 "
                "each, guest checkout: order MWS1050, total $74.87 (subtotal $56.97, "
                "shipping $14.95, processing $2.95). Shipping was NOT free — the cart "
                "asked to add 3 more bottles for free shipping.")
QUESTION = ("Buy 3 bottles of the Time & Tide Chardonnay as a guest and report the order "
            "number, the total, and the shipping charge.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the scored search for the wine, its product page, and the
    # guest checkout chain through the confirmation.
    judge.check("searched_time_tide",
                navigated_search_with(traj, "q", ["time", "tide", "chardonnay"]),
                "required: a /search visit whose q carries the task's wine tokens")
    check_visited_path(judge, traj, "visited_product_page", "/products/" + HANDLE)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (3 x $18.99 + $14.95 + $2.95)")
    judge.check("answer_shipping_charged",
                contains_money(answer, 14.95) and contains_phrase(answer, "shipping"),
                "expected the $14.95 shipping charge to be reported")
    # DB after-state: exactly one new guest order MWS1050 with 3 bottles.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"] - 14.95) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 3)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(total 74.87, shipping 14.95, 3 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == HANDLE
                and int(items_added[0]["quantity"]) == 3
                and abs(items_added[0]["unit_price"] - 18.99) < 0.005)
    judge.check("db_order_item_time_tide", ok_items,
                "expected one added order_items row for the Time & Tide Chardonnay (qty 3)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
