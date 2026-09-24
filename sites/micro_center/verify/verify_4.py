#!/usr/bin/env python3
"""Verify Micro Center--4.

Carol wants to cancel her most recent pending order but may buy its items locally later. Sign in as carol.d@test.com (password TestPass123!), check whether those items are in stock at Austin, TX, then cancel the order. Report its number, final status, refund total and the saved card it was paid with. Leave her other orders and cart unchanged.
"""
from verify_lib import (check_signed_in_as, check_only_tables_changed,
                        check_trajectory_identity, contains_amount, contains_count,
                        contains_phrase, db_query, final_answer, navigated_to_path,
                        navigated_to_product, order_by_number, run_verifier)

TASK_ID = "Micro Center--4"
EMAIL = "carol.d@test.com"
ORDER = "MC2608231112"
OTHER = "MC2607281111"
REFUND = 4034.84
NEW_SUBTOTAL = 74.98
ITEM_PIDS = (676998, 678427)
EXPECTED_CART = {350265: 1, 623409: 1}   # product_id -> qty after the rework


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_orders_page", navigated_to_path(traj, "/account/orders"),
                "required_path=/account/orders")
    judge.check("opened_recent_order_page",
                navigated_to_path(traj, f"/account/orders/{ORDER}"),
                f"required_path=/account/orders/{ORDER}")
    for pid in ITEM_PIDS:
        judge.check(f"checked_item_stock_{pid}",
                    navigated_to_product(traj, pid),
                    f"required_product_id={pid} (order item PDP for the Austin check)")
    judge.check("visited_payments_page", navigated_to_path(traj, "/account/payments"),
                "required_path=/account/payments (cross-check the saved card)")
    judge.check("answer_quotes_order_number", contains_phrase(answer, ORDER),
                f"expected_order_number={ORDER!r}")
    judge.check("answer_quotes_cancelled_status", contains_phrase(answer, "cancelled"),
                "expected_status=Cancelled")
    judge.check("answer_quotes_refund_total", contains_amount(answer, REFUND),
                f"expected_refund={REFUND}")
    judge.check("answer_names_paying_card",
                contains_phrase(answer, "4333") and contains_phrase(answer, "visa"),
                "expected: the saved Visa ending in 4333")
    order = order_by_number(after_db, ORDER)
    judge.check("order_status_cancelled",
                order is not None and order["status"] == "Cancelled",
                f"status={order['status'] if order else None!r}")
    other = order_by_number(after_db, OTHER)
    judge.check("earlier_order_untouched",
                other is not None and other["status"] == "Picked Up"
                and abs(other["total"] - 3678.65) < 0.011,
                f"status={other['status'] if other else None!r}")
    rows = db_query(after_db, "SELECT product_id, qty FROM cart_items WHERE user_id = 3")
    cart = {r["product_id"]: r["qty"] for r in rows}
    check_only_tables_changed(judge, initial_db, after_db, ("orders",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
