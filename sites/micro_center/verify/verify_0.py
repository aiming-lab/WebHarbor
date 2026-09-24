#!/usr/bin/env python3
"""Verify Micro Center--0.

I'm finishing Alice's pending pickup order and need to add a laptop for her daughter's first week at college. Sign in as alice.j@test.com (password TestPass123!), set the store to Rockville, MD, and choose a laptop under $600 that is in stock there. Keep her existing cart items that are available at Rockville, removing any that are out of stock, and complete the pickup order with her saved Visa. Report the order number and the total for the whole order.
"""
from verify_lib import (added_orders, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_amount, contains_phrase,
                        final_answer, navigated_confirmation, navigated_search_with,
                        navigated_to_path, navigated_to_product, order_items,
                        order_total_consistent, orders_of, run_verifier)

TASK_ID = "Micro Center--0"
EMAIL = "alice.j@test.com"
ROCKVILLE_STORE = "085"
LAPTOPS_UNDER_600_AT_ROCKVILLE = {
    676305: 399.99, 676307: 499.99, 678641: 499.99,
    683766: 559.60, 677547: 599.99, 678424: 599.99,
}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_store_locator",
                navigated_to_path(traj, "/site/stores/default.aspx"),
                "required_path=/site/stores/default.aspx")
    judge.check("searched_laptops", navigated_search_with(traj, "laptop"),
                "required_query_token=laptop")
    judge.check("visited_checkout_chain",
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
    alice = orders_of(after_db, email=EMAIL)
    judge.check("order_belongs_to_alice",
                any(o["order_number"] == order["order_number"] for o in alice),
                f"order_number={order['order_number']!r}")
    judge.check("order_is_pickup_at_rockville",
                order["method"] == "pickup" and str(order["store_id"]) == ROCKVILLE_STORE,
                f"method={order['method']!r}, store_id={order['store_id']!r}")
    items = order_items(order)
    picked = [i for i in items if int(i["product_id"]) in LAPTOPS_UNDER_600_AT_ROCKVILLE]
    judge.check("order_contains_qualifying_laptop", bool(picked),
                f"items={[(i['product_id'], i['price']) for i in items]!r}, "
                f"qualifying={list(LAPTOPS_UNDER_600_AT_ROCKVILLE)}")
    judge.check("order_totals_consistent", order_total_consistent(order),
                f"subtotal={order['subtotal']}, tax={order['tax']}, "
                f"total={order['total']}, shipping_fee={order['shipping_fee']}")
    judge.check("answer_quotes_order_number",
                contains_phrase(answer, order["order_number"]),
                f"expected_order_number={order['order_number']!r}")
    judge.check("answer_quotes_total",
                contains_amount(answer, order["total"]),
                f"expected_total={order['total']}")
    judge.check("visited_chosen_product_page",
                any(navigated_to_product(traj, int(i["product_id"])) for i in picked),
                f"picked={[(i['product_id'], i['name'][:40]) for i in picked]!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("orders", "cart_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
