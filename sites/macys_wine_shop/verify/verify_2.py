#!/usr/bin/env python3
"""Verify MacysWineShop--2: multi-constraint discovery (Spain + Red) + purchase.

Frozen ground truth (seed): filtering Shop All Wine with Color = Red and
Country = Spain leaves 11 wines; the highest customer rating among them is the
2023 Valdemacuco Tempranillo ($13.29, 5.0 stars, 1 review, 100% would
recommend, Rioja); buying 3 bottles as a guest gives subtotal $39.87, shipping
$14.95, processing $2.95, total $57.77; the order is MWS1050.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money, contains_phrase,
                        final_answer, navigated_collection_with_facets, navigated_to,
                        run_verifier, table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--2"
HANDLE = "2023-valdemacuco-tempranillo"
TOTAL = 57.77
GROUND_TRUTH = ("Shop All Wine filtered to Color = Red and Country = Spain leaves 11 "
                "wines; the highest-rated is the 2023 Valdemacuco Tempranillo ($13.29, "
                "5.0 out of 5, 1 review, 100% would recommend, Rioja). 3 bottles as a "
                "guest: order MWS1050, total $57.77 (subtotal $39.87, shipping $14.95, "
                "processing $2.95).")
QUESTION = ("Filter Shop All Wine to red wines from Spain, pick the highest-rated wine, "
            "verify its rating on its page, buy 3 bottles as a guest, and report the "
            "filtered count, the wine with its rating, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the filtered collection listing, the winner's product
    # page, and the guest checkout chain through the confirmation.
    judge.check("visited_spain_red_filtered_listing",
                navigated_collection_with_facets(traj, "all-wine",
                                                  {"color": "Red", "country": "Spain"}),
                "required: /collections/all-wine with both facet filters "
                "(color=Red, country=Spain)")
    check_visited_path(judge, traj, "visited_valdemacuco_page", "/products/" + HANDLE)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_filtered_count", contains_count(answer, 11),
                "expected the filtered result count 11")
    judge.check("answer_picked_wine", contains_phrase(answer, "Valdemacuco"),
                "expected the picked wine (Valdemacuco Tempranillo)")
    judge.check("answer_rating_facts",
                contains_phrase(answer, "5.0") and contains_phrase(answer, "100%"),
                "expected the rating facts (5.0 out of 5, 100% would recommend)")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (3 x $13.29 + $14.95 + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 with 3 bottles.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 3)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 (total 57.77, 3 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == HANDLE
                and int(items_added[0]["quantity"]) == 3
                and abs(items_added[0]["unit_price"] - 13.29) < 0.005)
    judge.check("db_order_item_valdemacuco", ok_items,
                "expected one added order_items row for the Valdemacuco Tempranillo (qty 3)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
