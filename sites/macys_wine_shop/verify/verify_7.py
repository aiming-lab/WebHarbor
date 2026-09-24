#!/usr/bin/env python3
"""Verify MacysWineShop--7: guest cart rules chain (3-bottle minimum -> 6-bottle free shipping).

Frozen ground truth (seed): with 2 bottles of the 2021 Valanda Tempranillo
($16.99) in a guest cart, the cart page shows 'Minimum 3 Bottles Required for
Checkout' with the Checkout button disabled and 'Add 4 bottles for free
shipping!'; at 3 bottles checkout unlocks with $14.95 shipping ('Add 3 bottles
for free shipping!'); at 6 bottles the note reads 'Free Shipping unlocked!' and
shipping is FREE. The placed guest order MWS1050 carries 6 Valanda bottles:
subtotal $101.94, shipping $0.00, processing $2.95, total $104.89.
"""

from review_common import fact

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_free, contains_money, contains_phrase,
                        final_answer, navigated_search_with, navigated_to, run_verifier,
                        table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--7"
VALANDA = "2021-valanda-tempranillo"
TOTAL = 104.89
GROUND_TRUTH = ("Cart rules: 'Minimum 3 Bottles Required for Checkout' (Checkout disabled "
                "below 3 bottles) and free shipping at 6+ bottles ('Add N bottles for free "
                "shipping!' -> 'Free Shipping unlocked!'). Order for 6 bottles of the 2021 "
                "Valanda Tempranillo: MWS1050, total $104.89 (subtotal $101.94, shipping "
                "FREE, processing $2.95).")
QUESTION = ("Start with 2 bottles of the Valanda Tempranillo in a guest cart, read the "
            "cart page's minimum and free-shipping rules, adjust the quantity until "
            "checkout unlocks and then until free shipping unlocks, place the order, and "
            "report both rules, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the Valanda page, the cart (where both rules are read),
    # and the guest checkout chain through the confirmation.
    judge.check("searched_valanda",
                navigated_search_with(traj, "q", ["valanda"]),
                "required: a /search visit locating the Valanda Tempranillo")
    check_visited_path(judge, traj, "visited_valanda_page", "/products/" + VALANDA)
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_minimum_rule",
                fact(answer, r'minimum|at least|requires?', r'(?:3|three)\s+(?:wine\s+)?bottles'),
                "expected the cart's minimum rule text 'Minimum 3 Bottles Required "
                "for Checkout'")
    judge.check("answer_free_shipping_rule",
                fact(answer, r'free shipping|shipping.{0,20}free', r'(?:6|six)\s*(?:\+|or more)?\s*bottles'),
                "expected the free-shipping rule (FREE shipping at 6 bottles)")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (6 x $16.99 + FREE shipping + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 with 6 bottles and
    # free shipping.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"]) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 6)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(total 104.89, free shipping, 6 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == VALANDA
                and int(items_added[0]["quantity"]) == 6
                and abs(items_added[0]["unit_price"] - 16.99) < 0.005)
    judge.check("db_order_item_valanda_qty6", ok_items,
                "expected one added order_items row for the Valanda Tempranillo (qty 6)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
