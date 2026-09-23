#!/usr/bin/env python3
"""Verify JCPenney--29."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--29"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_order_history", "/account/dashboard/orders")
    check_visited_path(judge, traj, "visited_order_detail", "/orders/JCP2609203008")
    check_visited_path(judge, traj, "visited_papell_product",
                       "/p/papell-boutique-womens-v-neck-short-sleeve-cap-evening-gown/ppr5008618161")
    # Frozen ground truth (seed DB): the order containing the Liz Claiborne Womens
    # Short Sleeve Midi Sweater Dress is JCP2609203008 — status Processing, total
    # $53.28, single item (the dress, $40.95). David's wish list holds the Papell
    # Boutique evening gown; its product page shows the price range $89.59 - $160.00.
    judge.check("answer_order_number", contains_phrase(answer, "JCP2609203008"),
                "expected order number JCP2609203008")
    judge.check("answer_order_status", contains_phrase(answer, "Processing"),
                "expected the order status Processing")
    judge.check("answer_order_total", contains_amount(answer, 53.28),
                "expected the order total $53.28")
    judge.check("answer_order_item", contains_all(answer, ["Short Sleeve Midi Sweater Dress", "40.95"]),
                "expected the Liz Claiborne midi sweater dress at $40.95")
    judge.check("answer_papell_price_range", contains_money(answer, [89.59, 160.00]),
                "expected the Papell Boutique gown price range $89.59 - $160.00")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
