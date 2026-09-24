#!/usr/bin/env python3
"""Verify Micro Center--13.

Pick up a 65-inch TV at the Chicago Micro Center today, ideally under $450;
check availability there, then complete an in-store pickup order for the
cheapest qualifying TV as a guest, and report the order number and total.

Frozen ground truth (seed DB): the only 65-inch TV under $450 with a Chicago
(store 151) "in stock" row is the 65UT7570PUB 65" Class 4K Ultra HD Smart LED
TV (678822, $399.99). Guest pickup order total = 399.99 * 1.0725 = $428.99.
"""
from verify_lib import (added_orders, check_only_tables_changed,
                        check_trajectory_identity, contains_amount, contains_phrase,
                        final_answer, in_stock_at, navigated_confirmation,
                        navigated_search_with, navigated_to_path, navigated_to_product,
                        order_items, order_total_consistent, product_by_id,
                        run_verifier)

TASK_ID = "Micro Center--13"
TV_PID = 678822
TV_PRICE = 399.99
TOTAL = 428.99
CHICAGO = "151"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_tvs", navigated_search_with(traj, "tv"),
                "required_query_token=tv")
    judge.check("visited_tv_product_page", navigated_to_product(traj, TV_PID),
                f"required_product_id={TV_PID} (65UT7570PUB)")
    judge.check("visited_pickup_checkout_chain",
                navigated_to_path(traj, "/checkout/mode")
                and navigated_to_path(traj, "/checkout/pickup")
                and navigated_to_path(traj, "/checkout/payment")
                and navigated_to_path(traj, "/checkout/review"),
                "required_paths=/checkout/mode,/checkout/pickup,"
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
    judge.check("order_is_pickup_at_chicago",
                order["method"] == "pickup" and str(order["store_id"]) == CHICAGO,
                f"method={order['method']!r}, store_id={order['store_id']!r}")
    items = order_items(order)
    tvs = [i for i in items if int(i["product_id"]) == TV_PID]
    judge.check("order_contains_qualifying_tv", bool(tvs),
                f"items={[(i['product_id'], i['name'][:40]) for i in items]!r}")
    judge.check("tv_in_stock_at_chicago",
                in_stock_at(after_db, TV_PID, CHICAGO),
                f"product={TV_PID} at store {CHICAGO}")
    judge.check("order_totals_consistent", order_total_consistent(order),
                f"subtotal={order['subtotal']}, tax={order['tax']}, total={order['total']}")
    judge.check("answer_quotes_order_number",
                contains_phrase(answer, order["order_number"]),
                f"expected_order_number={order['order_number']!r}")
    judge.check("answer_quotes_total", contains_amount(answer, TOTAL),
                f"expected_total={TOTAL}")
    check_only_tables_changed(judge, initial_db, after_db, ("orders",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
