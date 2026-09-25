#!/usr/bin/env python3
"""Verify Micro Center--8.

Without signing in, buy two of the cheapest 120mm case fans on the site and have them shipped to Dana Chen, 350 Fifth Avenue, New York, NY 10118 with two-day shipping. Pay with any 16-digit card number. Report the order number and the total including shipping.
"""
from verify_lib import (added_orders, check_only_tables_changed,
                        check_trajectory_identity, contains_amount, contains_phrase,
                        final_answer, navigated_confirmation, navigated_search_with,
                        navigated_to_path, navigated_to_product, order_items,
                        order_total_consistent, run_verifier)

TASK_ID = "Micro Center--8"
FAN_PID = 325743
FAN_PRICE = 7.99
TOTAL = 30.13
SHIP_TO_TOKENS = ("dana chen", "350 fifth avenue")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_case_fans", navigated_search_with(traj, "fan"),
                "required_query_token=fan")
    judge.check("visited_fan_product_page", navigated_to_product(traj, FAN_PID),
                f"required_product_id={FAN_PID} (Advance CF-12LB)")
    judge.check("visited_shipping_checkout_chain",
                navigated_to_path(traj, "/checkout/mode")
                and navigated_to_path(traj, "/checkout/shipping")
                and navigated_to_path(traj, "/checkout/payment")
                and navigated_to_path(traj, "/checkout/review"),
                "required_paths=/checkout/mode,/checkout/shipping,"
                "/checkout/payment,/checkout/review")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required_path=/checkout/confirmation")
    new_orders = added_orders(after_db, initial_db)
    judge.check("exactly_one_new_order", len(new_orders) == 1,
                f"new_orders={[o['order_number'] for o in new_orders]!r}")
    if not new_orders:
        return
    order = new_orders[0]
    judge.check("order_is_guest", order["user_id"] == 0,
                f"user_id={order['user_id']!r}")
    judge.check("order_is_shipping", order["method"] == "shipping",
                f"method={order['method']!r}")
    items = order_items(order)
    fans = [i for i in items if int(i["product_id"]) == FAN_PID]
    judge.check("order_contains_two_fans",
                sum(i["qty"] for i in fans) == 2,
                f"items={[(i['product_id'], i['qty']) for i in items]!r}")
    judge.check("order_ships_to_dana_chen",
                all(contains_phrase(order["ship_to"] or "", t) for t in SHIP_TO_TOKENS),
                f"ship_to={order['ship_to']!r}")
    judge.check("order_totals_consistent", order_total_consistent(order),
                f"subtotal={order['subtotal']}, tax={order['tax']}, "
                f"shipping_fee={order['shipping_fee']}, total={order['total']}")
    judge.check("answer_quotes_order_number",
                contains_phrase(answer, order["order_number"]),
                f"expected_order_number={order['order_number']!r}")
    judge.check("answer_quotes_total", contains_amount(answer, TOTAL),
                f"expected_total={TOTAL}")
    check_only_tables_changed(judge, initial_db, after_db, ("orders",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
