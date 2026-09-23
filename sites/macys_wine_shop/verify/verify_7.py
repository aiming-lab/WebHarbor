#!/usr/bin/env python3
"""Verify MacysWineShop--7: Golden State Essentials Case contents"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--7"

CASE_BOTTLES = [
    "2021 Free Flight Red Blend",
    "2023 House Party Pinot Grigio",
    "2022 Redland Ranch Reserve Zinfandel",
    "2024 Misirlou Chardonnay",
    "2024 Wolfson Cellars Sauvignon Blanc",
    "2023 Hats & Hides Cabernet Sauvignon",
]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_case_product_page",
                       "/products/golden-state-essentials-case")
    # Frozen ground truth: 6 bottles in numbered order, 3 red / 3 white,
    # 6-pack per-bottle price $12.74.
    for i, name in enumerate(CASE_BOTTLES):
        judge.check(f"answer_case_bottle_{i + 1}", contains_phrase(answer, name),
                    f"expected case bottle {i + 1}: '{name}'")
    judge.check("answer_red_white_split",
                contains_phrase(answer, "3 red") and contains_phrase(answer, "3 white"),
                "expected the case split: 3 red and 3 white")
    judge.check("answer_per_bottle_price", contains_money(answer, 12.74),
                "expected the 6-pack per-bottle price $12.74")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
