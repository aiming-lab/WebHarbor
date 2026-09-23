#!/usr/bin/env python3
"""Verify MacysWineShop--3: wine sets under $50, cheapest set"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--3"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_under_50_collection_sorted",
                navigated_listing_sorted(traj, "/collections/wine-sets-under-50", "price-ascending"),
                "required: /collections/wine-sets-under-50?sort_by=price-ascending")
    judge.check("opened_cheapest_set_page",
                navigated_to_path(traj, "/products/festive-vines-pumpkin-spice-chardonnay-3-pack"),
                "required: the cheapest set's product page")
    # Frozen ground truth: 31 sets; cheapest = Festive Vines Pumpkin Spice Chardonnay
    # 3-Pack, $33.12, 3 bottles.
    judge.check("answer_set_count", contains_count(answer, 31),
                "expected 31 sets in the collection")
    judge.check("answer_cheapest_name", contains_phrase(answer, "Festive Vines Pumpkin Spice Chardonnay"),
                "expected cheapest set 'Festive Vines Pumpkin Spice Chardonnay 3-Pack'")
    judge.check("answer_cheapest_price", contains_money(answer, 33.12),
                "expected the cheapest set price $33.12")
    judge.check("answer_bottle_count", contains_count(answer, 3),
                "expected the cheapest set to contain 3 bottles")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
