#!/usr/bin/env python3
"""Verify MacysWineShop--5: bob's logged-in purchase with saved address + card.

Frozen ground truth (seed): bob.c@test.com (password TestPass123!) has one
saved address in Seattle, WA and one saved Visa ending in 1881; his seeded
cart holds the Cabs For Grabs Trio (3 bottles, $67.47) and 3 bottles of the
2021 Valanda Tempranillo ($16.99); adding 2 more Valanda bottles takes the
cart to 8 bottles (free shipping), and checking out with the saved address and
card places order MWS1050 for bob with subtotal $152.42 and total $155.37.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_money,
                        contains_phrase, final_answer, navigated_search_with, navigated_to,
                        run_verifier, table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--5"
BOB = "bob.c@test.com"
VALANDA = "2021-valanda-tempranillo"
TRIO = "cabs-for-grabs-trio"
TOTAL = 155.37
GROUND_TRUTH = ("Bob's saved address is in Seattle (1201 3rd Ave, Unit 19) and his saved "
                "card is the Visa ending in 1881. Adding 2 more bottles of the 2021 Valanda "
                "Tempranillo to the seeded cart (Trio + 3 bottles) and checking out with "
                "the saved details: order MWS1050, total $155.37 (subtotal $152.42, FREE "
                "shipping at 8 bottles, processing $2.95).")
QUESTION = ("Log in as bob, check the saved address and card, add 2 more bottles of the "
            "Valanda Tempranillo, check out with the saved details, and report the saved "
            "address city, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB)
    # navigation gates: the account surfaces the task names, the Valanda page,
    # and the checkout chain through the confirmation.
    check_visited_path(judge, traj, "visited_account_addresses", "/account/addresses")
    check_visited_path(judge, traj, "visited_account_payment", "/account/payment")
    judge.check("searched_valanda",
                navigated_search_with(traj, "q", ["valanda"]),
                "required: a /search visit locating the Valanda Tempranillo")
    check_visited_path(judge, traj, "visited_valanda_page", "/products/" + VALANDA)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_saved_address_city", contains_phrase(answer, "Seattle"),
                "expected the saved address city Seattle")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (subtotal $152.42 + FREE shipping + $2.95)")
    # DB after-state: exactly one new order for bob (MWS1050) holding the Trio
    # and 5 Valanda bottles (his seeded cart rows are consumed).
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and int(orders_added[0]["user_id"]) == 2
                 and str(orders_added[0]["state"]) == "WA"
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"]) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 8)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added order row MWS1050 (bob, WA, total 155.37, "
                "8 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    by_handle = {row["product_handle"]: row for row in items_added}
    ok_items = (len(items_added) == 2 and TRIO in by_handle and VALANDA in by_handle
                and int(by_handle[TRIO]["quantity"]) == 1
                and int(by_handle[VALANDA]["quantity"]) == 5)
    judge.check("db_order_items", ok_items,
                "expected added order_items rows: Trio qty 1 + Valanda qty 5")
    cart = table_delta(initial_db, after_db, "cart_items")
    ok_cart = len(cart["removed"]) == 2 and len(cart["added"]) == 0 and len(cart["changed"]) == 0
    judge.check("db_bob_cart_consumed", ok_cart,
                "expected bob's two seeded cart rows removed on order placement")
    check_only_tables_changed(judge, initial_db, after_db,
                               {"orders", "order_items", "cart_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
