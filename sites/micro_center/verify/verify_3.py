#!/usr/bin/env python3
"""Verify Micro Center--3.

Two family members in Texas want the same graphics card for a build this weekend. Find a graphics card in stock at both Dallas and Houston, then add one to Bob's pending order and complete pickup checkout at Dallas (bob.c@test.com / TestPass123!). Keep his existing cart items and report the order number.
"""
from verify_lib import (added_orders, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_phrase, final_answer,
                        in_stock_at, navigated_confirmation, navigated_search_with,
                        navigated_to_path, order_items, orders_of, product_by_id,
                        run_verifier)

TASK_ID = "Micro Center--3"
EMAIL = "bob.c@test.com"
DALLAS = "131"
HOUSTON = "155"
GPU_BOTH_TX = (641955, 689783, 681510, 691225, 682498, 667264, 667476, 643624,
               675394, 633840, 676898, 639235, 668351, 676388, 670504, 685514,
               690046, 675143, 690262, 690453, 689736, 690032)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("searched_graphics_card", navigated_search_with(traj, "graphics"),
                "required_query_token=graphics")
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
    bob = orders_of(after_db, email=EMAIL)
    judge.check("order_belongs_to_bob",
                any(o["order_number"] == order["order_number"] for o in bob),
                f"order_number={order['order_number']!r}")
    judge.check("order_is_pickup_at_dallas",
                order["method"] == "pickup" and str(order["store_id"]) == DALLAS,
                f"method={order['method']!r}, store_id={order['store_id']!r}")
    items = order_items(order)
    qualifying = []
    for item in items:
        pid = int(item["product_id"])
        if pid in GPU_BOTH_TX:
            row = product_by_id(after_db, pid)
            if (in_stock_at(after_db, pid, DALLAS)
                    and in_stock_at(after_db, pid, HOUSTON)
                    and row and ("geforce" in row["name"].lower()
                                 or "radeon" in row["name"].lower())):
                qualifying.append(pid)
    judge.check("order_contains_dual_stock_gpu", bool(qualifying),
                f"items={[(i['product_id'], i['name'][:40]) for i in items]!r}")
    judge.check("answer_quotes_order_number",
                contains_phrase(answer, order["order_number"]),
                f"expected_order_number={order['order_number']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("orders", "cart_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
