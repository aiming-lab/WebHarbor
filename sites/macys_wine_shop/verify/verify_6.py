#!/usr/bin/env python3
"""Verify MacysWineShop--6: carol's purchase to a NEW address with a NEW card.

Frozen ground truth (seed): carol.d@test.com (password TestPass123!) has one
seeded address (Chicago) and one seeded Amex; her cart holds 2 bottles of the
2023 Closed Window Pinot Noir Willamette Valley ($19.99) and the Martha's
Chardonnay Collection white/6-pack ($86.65) = 8 bottles. The task adds address
'Kayla Davis, 118 Larimer St, Apt 4, Denver, CO 80204, (303) 555-0148' (NOT
default) and checks out shipping to it with a new Mastercard ending in 2222:
order MWS1050 for carol, subtotal $126.63, FREE shipping (8 bottles),
processing $2.95, total $129.58.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_money,
                        contains_phrase, final_answer, input_texts,
                        navigated_to, run_verifier, table_delta, table_columns,
                        advisory_llm_answer)

TASK_ID = "MacysWineShop--6"
CAROL = "carol.d@test.com"
CLOSED_WINDOW = "2023-closed-window-pinot-noir-willamette-valley"
MARTHAS = "marthas-chardonnay-collection"
TOTAL = 129.58
NEW_ADDRESS = {"full_name": "Kayla Davis", "line1": "118 Larimer St", "line2": "Apt 4",
               "city": "Denver", "state": "CO", "zip_code": "80204"}
GROUND_TRUTH = ("Added a second address (Kayla Davis, 118 Larimer St, Apt 4, Denver, CO "
                "80204) and checked carol's cart (2x Closed Window Pinot Noir + the "
                "Martha's Chardonnay Collection 6-pack) out to it with a new Mastercard "
                "ending in 2222: order MWS1050, total $129.58 (subtotal $126.63, FREE "
                "shipping at 8 bottles, processing $2.95).")
QUESTION = ("Log in as carol, add the given second shipping address, check out the cart "
            "to the new address paying with the new card, and report the order number "
            "and total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL)
    # navigation gates: the address book (where the new address is added), the
    # cart, and the checkout chain shipping to the NEW address.
    check_visited_path(judge, traj, "visited_account_addresses", "/account/addresses")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # the new address fields must have been entered during the run
    inputs = input_texts(traj)
    for field, value in NEW_ADDRESS.items():
        if field == "state":
            continue  # state is a <select>, checked via the DB row below
        judge.check(f"entered_new_address_{field}",
                    any(value in v for v in inputs),
                    f"expected {value!r} in an input step; observed={inputs!r}")
    # answer checks against the frozen ground truth
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} ($126.63 + FREE shipping + $2.95)")
    # DB after-state: exactly one added address row for carol (not default),
    # one new order MWS1050 for carol shipped to that address, paid with the
    # new card, holding her two seeded cart items.
    acols = table_columns(after_db, "addresses")
    addr_added = [dict(zip(acols, row)) for row in table_delta(initial_db, after_db, "addresses")["added"]]
    ok_addr = (len(addr_added) == 1 and int(addr_added[0]["user_id"]) == 3
               and addr_added[0]["full_name"] == NEW_ADDRESS["full_name"]
               and addr_added[0]["line1"] == NEW_ADDRESS["line1"]
               and addr_added[0]["line2"] == NEW_ADDRESS["line2"]
               and addr_added[0]["city"] == NEW_ADDRESS["city"]
               and addr_added[0]["state"] == NEW_ADDRESS["state"]
               and addr_added[0]["zip_code"] == NEW_ADDRESS["zip_code"]
               and not addr_added[0]["is_default"])
    judge.check("db_new_address_row", ok_addr,
                f"expected exactly one added address row for carol: {NEW_ADDRESS}")
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and int(orders_added[0]["user_id"]) == 3
                 and orders_added[0]["address_line1"] == NEW_ADDRESS["line1"]
                 and orders_added[0]["city"] == NEW_ADDRESS["city"]
                 and str(orders_added[0]["state"]) == "CO"
                 and "2222" in str(orders_added[0]["payment_label"])
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 8)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added order row MWS1050 (carol, new Denver address, "
                "Mastercard 2222, total 129.58, 8 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    by_handle = {row["product_handle"]: row for row in items_added}
    ok_items = (len(items_added) == 2 and CLOSED_WINDOW in by_handle and MARTHAS in by_handle
                and int(by_handle[CLOSED_WINDOW]["quantity"]) == 2
                and int(by_handle[MARTHAS]["quantity"]) == 1)
    judge.check("db_order_items", ok_items,
                "expected added order_items rows: Closed Window qty 2 + Martha's 6-pack qty 1")
    cart = table_delta(initial_db, after_db, "cart_items")
    ok_cart = len(cart["removed"]) == 2 and len(cart["added"]) == 0 and len(cart["changed"]) == 0
    judge.check("db_carol_cart_consumed", ok_cart,
                "expected carol's two seeded cart rows removed on order placement")
    check_only_tables_changed(judge, initial_db, after_db,
                               {"addresses", "orders", "order_items", "cart_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
