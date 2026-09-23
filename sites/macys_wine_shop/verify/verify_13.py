#!/usr/bin/env python3
"""Verify MacysWineShop--13: review-driven purchase of the most-reviewed Chardonnay.

Frozen ground truth (seed): the Chardonnay with the most customer reviews on
the site is the 2023 Ahlma Chardonnay Reserva — 11 reviews (the site's
highest review count), 4.6 out of 5 average, 100% would recommend, $13.29
per bottle. 3 bottles as a guest: order MWS1050, subtotal
$39.87, shipping $14.95, processing $2.95, total $57.77.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money, contains_percent,
                        contains_phrase, final_answer, navigated_search_with, navigated_to,
                        run_verifier, table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--13"
AHLMA = "2023-ahlma-chardonnay-reserva"
TOTAL = 57.77
GROUND_TRUTH = ("The most-reviewed Chardonnay is the 2023 Ahlma Chardonnay Reserva with "
                "11 reviews — 4.6 out of 5 average and 100% would recommend it ($13.29). "
                "3 bottles as a guest: order MWS1050, total $57.77 (subtotal $39.87, "
                "shipping $14.95, processing $2.95).")
QUESTION = ("Find the Chardonnay with the most customer reviews, read its review summary "
            "(average rating, review count, recommend percentage), buy 3 bottles as a "
            "guest, and report the wine with its rating facts, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the chardonnay search, the most-reviewed wine's page
    # (where the review summary is read), and the guest checkout chain.
    judge.check("searched_chardonnay",
                navigated_search_with(traj, "q", ["chardonnay"]),
                "required: a /search visit for chardonnays")
    check_visited_path(judge, traj, "visited_ahlma_page", "/products/" + AHLMA)
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_wine_named",
                contains_phrase(answer, "Ahlma"),
                "expected the most-reviewed wine (Ahlma Chardonnay Reserva) to be named")
    judge.check("answer_review_count", contains_count(answer, 11),
                "expected the 11-review count")
    judge.check("answer_rating", contains_phrase(answer, "4.6"),
                "expected the 4.6 out of 5 average rating")
    judge.check("answer_recommend_percent", contains_percent(answer, 100),
                "expected the 100% would-recommend percentage")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (3 x $13.29 + $14.95 + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 holding 3 Ahlma
    # bottles.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 3)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(total 57.77, 3 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == AHLMA
                and int(items_added[0]["quantity"]) == 3
                and abs(items_added[0]["unit_price"] - 13.29) < 0.005)
    judge.check("db_order_item_ahlma", ok_items,
                "expected one added order_items row for the Ahlma Chardonnay Reserva (qty 3)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
