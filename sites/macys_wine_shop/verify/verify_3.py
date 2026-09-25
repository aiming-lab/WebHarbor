#!/usr/bin/env python3
"""Verify MacysWineShop--3: Golden State Essentials 6-pack vs 12-pack value buy.

Frozen ground truth (seed): the Golden State Essentials Case sells a 6-pack at
$76.45 ($12.74 per bottle, 3 Red + 3 White) and a 12-pack at $143.90 ($11.99
per bottle, 6 Red + 6 White); the 12-pack has the lower per-bottle price and is
the one bought; the case bottles are the 2021 Free Flight Red Blend, 2023 House
Party Pinot Grigio, 2022 Redland Ranch Reserve Zinfandel, 2024 Misirlou
Chardonnay, 2024 Wolfson Cellars Sauvignon Blanc, and 2023 Hats & Hides
Cabernet Sauvignon; with 12 bottles shipping is FREE, so the placed guest
order MWS1050 totals $143.90 + $2.95 = $146.85.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money, contains_phrase, final_answer,
                        navigated_search_with, navigated_to, run_verifier, table_delta,
                        table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--3"
HANDLE = "golden-state-essentials-case"
TOTAL = 146.85
GROUND_TRUTH = ("Golden State Essentials Case: the 6-pack costs $76.45 ($12.74 per "
                "bottle), the 12-pack costs $143.90 ($11.99 per bottle) — the 12-pack is "
                "the better per-bottle value; its 12 bottles (6 Red, 6 White) are the Free "
                "Flight Red Blend, House Party Pinot Grigio, Redland Ranch Reserve "
                "Zinfandel, Misirlou Chardonnay, Wolfson Cellars Sauvignon Blanc and Hats "
                "& Hides Cabernet Sauvignon. Order MWS1050 total $146.85 (subtotal $143.90, "
                "FREE shipping, processing $2.95).")
QUESTION = ("Compare the Golden State Essentials Case 6-pack and 12-pack on case price "
            "and per-bottle price, buy the better per-bottle value, and report both "
            "prices, the case contents, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the case product page (pack options + contents), the
    # cart, and the guest checkout chain through the confirmation.
    judge.check("searched_golden_state",
                navigated_search_with(traj, "q", ["golden", "state"]),
                "required: a /search visit locating the Golden State case")
    check_visited_path(judge, traj, "visited_case_page", "/products/" + HANDLE)
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_6pack_prices",
                contains_money(answer, 76.45) and contains_money(answer, 12.74),
                "expected the 6-pack case price $76.45 and per-bottle $12.74")
    judge.check("answer_12pack_prices",
                contains_money(answer, 143.90) and contains_money(answer, 11.99),
                "expected the 12-pack case price $143.90 and per-bottle $11.99")
    judge.check("answer_case_contents",
                contains_phrase(answer, "Free Flight") and contains_phrase(answer, "Zinfandel")
                and contains_phrase(answer, "Cabernet Sauvignon"),
                "expected named case bottles (Free Flight Red Blend, Redland Ranch Reserve "
                "Zinfandel, Hats & Hides Cabernet Sauvignon, ...)")
    judge.check("answer_bought_12pack", contains_phrase(answer, "12-pack"),
                "expected the answer to state the 12-pack was bought")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} ($143.90 + FREE shipping + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 holding the 12-pack.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"]) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 12)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(total 146.85, free shipping, 12 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == HANDLE
                and "12" in str(items_added[0]["variant_title"])
                and int(items_added[0]["quantity"]) == 1
                and abs(items_added[0]["unit_price"] - 143.90) < 0.005
                and int(items_added[0]["bottle_count"]) == 12)
    judge.check("db_order_item_12pack", ok_items,
                "expected one added order_items row for the 12-pack case (12 bottles)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
