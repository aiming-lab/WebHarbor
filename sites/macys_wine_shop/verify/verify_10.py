#!/usr/bin/env python3
"""Verify MacysWineShop--10: Cabs For Grabs Trio contents + per-bottle price"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--10"

TRIO_BOTTLES = [
    "2021 Cremaschi Furlotti Gran Reserva Cabernet Sauvignon",
    "2024 Magistrale Cabernet Sauvignon I.G.T. Veneto",
    "2023 Fairweather Cabernet Sauvignon",
]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_trio_product_page", "/products/cabs-for-grabs-trio")
    # Frozen ground truth: 3 bottles; per-bottle price $22.49 for the 3-pack.
    judge.check("answer_bottle_count", contains_count(answer, 3),
                "expected the trio to contain 3 bottles")
    for i, name in enumerate(TRIO_BOTTLES):
        judge.check(f"answer_trio_bottle_{i + 1}", contains_phrase(answer, name),
                    f"expected trio bottle {i + 1}: '{name}'")
    judge.check("answer_per_bottle_price", contains_money(answer, 22.49),
                "expected the 3-pack per-bottle price $22.49")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
