#!/usr/bin/env python3
"""Verify MacysWineShop--12: award comparison — House Party Moscato vs Misirlou Chardonnay.

Frozen ground truth (seed): the 2024 House Party Moscato ($11.89) carries Gold,
2026 Critics Challenge International Wine Competition, ABV 11.0%; the 2024
Misirlou Chardonnay ($13.99) carries Gold, 2025 Harvest Challenge
International Wine Competition, ABV 13.5%. The cheaper Moscato is bought — 6
bottles to unlock free shipping ('Free Shipping unlocked!'): guest order
MWS1050, subtotal $71.34, shipping $0.00, processing $2.95, total $74.29.
"""

from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_money,
                        contains_phrase, final_answer, navigated_search_with, navigated_to,
                        run_verifier, table_delta, table_columns, advisory_llm_answer)

TASK_ID = "MacysWineShop--12"
MOSCATO = "2024-house-party-moscato"
MISIRLOU = "2024-misirlou-chardonnay"
TOTAL = 74.29
GROUND_TRUTH = ("2024 House Party Moscato ($11.89): Gold, 2026 Critics Challenge "
                "International Wine Competition, ABV 11.0%. 2024 Misirlou Chardonnay "
                "($13.99): Gold, 2025 Harvest Challenge International Wine Competition, "
                "ABV 13.5%. Bought the cheaper Moscato — 6 bottles unlock free shipping: "
                "order MWS1050, total $74.29 (subtotal $71.34, shipping FREE, processing "
                "$2.95).")
QUESTION = ("Compare the two award winners' medals, competitions and ABV, buy 6 bottles "
            "of the cheaper one as a guest to unlock free shipping, and report both wines' "
            "facts, which one you bought, the order number, and the total.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: BOTH compared product pages, the cart (free-shipping
    # unlock), and the guest checkout chain through the confirmation.
    judge.check("searched_moscato",
                navigated_search_with(traj, "q", ["house", "party"]),
                "required: a /search visit locating the House Party Moscato")
    check_visited_path(judge, traj, "visited_moscato_page", "/products/" + MOSCATO)
    judge.check("searched_misirlou",
                navigated_search_with(traj, "q", ["misirlou"]),
                "required: a /search visit locating the Misirlou Chardonnay")
    check_visited_path(judge, traj, "visited_misirlou_page", "/products/" + MISIRLOU)
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout_information", "/checkout/information")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                navigated_to(traj, "/checkout/confirmation/MWS1050"),
                "required: the confirmation page for order MWS1050")
    # answer checks against the frozen ground truth
    judge.check("answer_moscato_award",
                contains_phrase(answer, "Critics Challenge") and contains_phrase(answer, "2026"),
                "expected the Moscato's Gold 2026 Critics Challenge award")
    judge.check("answer_misirlou_award",
                contains_phrase(answer, "Harvest Challenge") and contains_phrase(answer, "2025"),
                "expected the Misirlou's Gold 2025 Harvest Challenge award")
    judge.check("answer_abv_both",
                contains_phrase(answer, "11.0") and contains_phrase(answer, "13.5"),
                "expected both ABV values (11.0% and 13.5%)")
    judge.check("answer_bought_cheaper",
                contains_phrase(answer, "Moscato") and contains_money(answer, 11.89),
                "expected the answer to name the cheaper Moscato as the one bought")
    judge.check("answer_free_shipping",
                contains_phrase(answer, "free shipping") or contains_phrase(answer, "FREE"),
                "expected the free-shipping unlock to be reported")
    judge.check("answer_order_number", contains_phrase(answer, "MWS1050"),
                "expected the new order number MWS1050")
    judge.check("answer_total", contains_money(answer, TOTAL),
                f"expected the total ${TOTAL:.2f} (6 x $11.89 + FREE shipping + $2.95)")
    # DB after-state: exactly one new guest order MWS1050 with 6 Moscato
    # bottles and free shipping.
    ocols = table_columns(after_db, "orders")
    orders_added = [dict(zip(ocols, row)) for row in table_delta(initial_db, after_db, "orders")["added"]]
    ok_orders = (len(orders_added) == 1 and orders_added[0]["order_number"] == "MWS1050"
                 and orders_added[0]["user_id"] is None
                 and abs(orders_added[0]["total"] - TOTAL) < 0.005
                 and abs(orders_added[0]["shipping"]) < 0.005
                 and int(orders_added[0]["bottle_count"]) == 6)
    judge.check("db_new_order_row", ok_orders,
                "expected exactly one added guest order row MWS1050 "
                "(total 74.29, free shipping, 6 bottles)")
    icols = table_columns(after_db, "order_items")
    items_added = [dict(zip(icols, row)) for row in table_delta(initial_db, after_db, "order_items")["added"]]
    ok_items = (len(items_added) == 1 and items_added[0]["product_handle"] == MOSCATO
                and int(items_added[0]["quantity"]) == 6
                and abs(items_added[0]["unit_price"] - 11.89) < 0.005)
    judge.check("db_order_item_moscato_qty6", ok_items,
                "expected one added order_items row for the House Party Moscato (qty 6)")
    check_only_tables_changed(judge, initial_db, after_db, {"orders", "order_items"})
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
