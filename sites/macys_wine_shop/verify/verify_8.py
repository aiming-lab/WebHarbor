#!/usr/bin/env python3
"""Verify MacysWineShop--8: david's order-history lookup + exact reorder.

Frozen ground truth (seed): david.k@test.com (password TestPass123!) has one
order still Processing — MWS1048, the California Red Wine Odyssey (red /
6-pack) at $92.60, total $95.55 (free shipping at 6 bottles); his seeded cart
holds the Oh-So-Sweet Case and 2 bottles of the Della Flora Organic Cabernet,
which the task removes; reordering exactly the 6-pack places order MWS1050
for david with subtotal $92.60, shipping $0.00, processing $2.95, total $95.55
— the same total as the original order.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_money,
                        contains_phrase, final_answer, navigated_search_with, navigated_to,
                        run_verifier, table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--8"
DAVID = "david.k@test.com"
ODYSSEY = "california-red-wine-odyssey"
OLD_ORDER = "MWS1048"
TOTAL = 95.55
GROUND_TRUTH = ("The order still Processing is MWS1048 — California Red Wine Odyssey "
                "(red / 6-pack) at $92.60, total $95.55. After clearing the other cart "
                "items and reordering exactly that six-pack, the new order is MWS1050 "
                "with the same total $95.55 (subtotal $92.60, FREE shipping at 6 bottles, "
                "processing $2.95).")
QUESTION = ("Log in as david, find the still-Processing order, reorder exactly its item "
            "with the cart cleared of everything else, and report both order numbers "
            "with their totals.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, DAVID)
    # navigation gates: the order history, the Processing order's detail page,
    # the reordered product's page, the cart (where the other rows are
    # removed), and the checkout chain through the confirmation.
    check_visited_path(judge, traj, "visited_account_orders", "/account/orders")
    check_visited_path(judge, traj, "visited_processing_order_detail",
                       f"/account/orders/{OLD_ORDER}")
    judge.check("searched_odyssey",
                navigated_search_with(traj, "q", ["california", "wine", "odyssey"]),
                "required: a /search visit locating the California Red Wine Odyssey")
    check_visited_path(judge, traj, "visited_odyssey_page", "/products/" + ODYSSEY)
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_old_order_number", contains_phrase(answer, OLD_ORDER),
                "expected the old order number MWS1048")
    judge.check("answer_old_order_total", contains_money(answer, 95.55),
                "expected the old order total $95.55")
    judge.check("answer_new_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_new_order_total", contains_money(answer, TOTAL),
                f"expected the new order total ${TOTAL:.2f}")
    # DB after-state: exactly one new order MWS1050 for david holding ONLY the
    # odyssey 6-pack; david's two seeded cart rows are consumed.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and int(orders_added[0]["user_id"]) == 4
                 and str(orders_added[0]["state"]) == "NY"
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"]) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 6)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added order row MWS1050 (david, NY, total 95.55, "
                "6 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == ODYSSEY
                and "6" in str(items_added[0]["variant_title"])
                and int(items_added[0]["quantity"]) == 1
                and abs(items_added[0]["unit_price"] - 92.60) < 0.005
                and int(items_added[0]["bottle_count"]) == 6)
    judge.check("db_order_item_odyssey_6pack", ok_items,
                "expected one added order_items row for the odyssey red / 6-pack only")
    cart = table_delta(initial_db, after_db, "cart_items")
    ok_cart = len(cart["removed"]) == 2 and len(cart["added"]) == 0 and len(cart["changed"]) == 0
    judge.check("db_david_cart_consumed", ok_cart,
                "expected david's two seeded cart rows removed (cleared then reordered)")
    check_only_tables_changed(judge, initial_db, after_db,
                               {"orders", "order_items", "cart_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
