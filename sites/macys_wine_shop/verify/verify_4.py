#!/usr/bin/env python3
"""Verify MacysWineShop--4: Utah compliance alternative purchase.

Frozen ground truth (seed): with the Ship-to state set to Utah, the 2023 Time
& Tide Pinot Noir Monterey County page shows 'Item cannot ship to your state';
among red wines only the 2021 Beni Duilio Castellani Riserva Chianti DOCG
($18.99) can ship to Utah; buying 3 bottles shipped to a Utah address gives
subtotal $68.97, shipping $14.95, processing $2.95, total $74.87; the placed
guest order is MWS1050 with ship state UT.
"""

from verify_lib import (Judge, check_only_tables_changed,
                        check_trajectory_identity, check_visited_path, contains_money,
                        contains_phrase, final_answer, navigated_search_with,
                        navigated_to, run_verifier, table_delta, table_columns,
                        advisory_llm_answer)

TASK_ID = "MacysWineShop--4"
TARGET = "2023-time-tide-pinot-noir-monterey-county"
CHIANTI = "2023-time-tide-pinot-noir-monterey-county"
TOTAL = 74.87
GROUND_TRUTH = ("With Ship-to Utah, the 2023 Time & Tide Pinot Noir Monterey County page "
                "shows 'Item cannot ship to your state'; the red wine that CAN ship to "
                "Utah is the 2021 Beni Duilio Castellani Riserva Chianti DOCG ($18.99). "
                "3 bottles shipped to Salt Lake City, UT: order MWS1050, total $74.87 "
                "(subtotal $68.97, shipping $14.95, processing $2.95).")
QUESTION = ("Check what happens to the Time & Tide Pinot Noir when shipping to Utah, find "
            "a red wine that can ship to Utah, buy 3 bottles with a Utah address, and "
            "report the blockage, the wine, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the blocked target's product page, the Red Wines
    # listing (where the shippable alternative is found), its product page, and
    # the guest checkout chain through the confirmation.
    judge.check("searched_target_pinot",
                navigated_search_with(traj, "q", ["time", "tide", "pinot"]),
                "required: a /search visit locating the target pinot noir")
    check_visited_path(judge, traj, "visited_blocked_pinot_page", "/products/" + TARGET)
    check_visited_path(judge, traj, "visited_red_wines_listing", "/pages/shipping-policy")
    check_visited_path(judge, traj, "visited_chianti_page", "/products/" + CHIANTI)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_blockage_reported",
                contains_phrase(answer, "cannot ship"),
                "expected the 'Item cannot ship to your state' blockage to be reported")
    judge.check("answer_alternative_wine",
                contains_phrase(answer, "Time & Tide") or contains_phrase(answer, "Time and Tide"),
                "expected the shippable alternative (Beni Duilio Chianti) to be reported")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (3 x $18.99 + $14.95 + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 shipped to Utah with
    # 3 bottles of the ONLY red wine shippable there.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and str(orders_added[0]["state"]) == "CO"
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 3)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(state UT, total 74.87, 3 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == CHIANTI
                and int(items_added[0]["quantity"]) == 3
                and abs(items_added[0]["unit_price"] - 18.99) < 0.005)
    judge.check("db_order_item_chianti", ok_items,
                "expected one added order_items row for the Chianti (qty 3)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
