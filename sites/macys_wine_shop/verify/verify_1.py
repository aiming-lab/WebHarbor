#!/usr/bin/env python3
"""Verify MacysWineShop--1: moscato search, cheapest and most expensive"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--1"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_search_with_moscato",
                navigated_search_with(traj, "q", ["moscato"]),
                "required: /search?q=moscato")
    judge.check("search_sorted_price_ascending",
                navigated_listing_sorted(traj, "/search", "price-ascending"),
                "required: sort_by=price-ascending on the search listing")
    # Frozen ground truth: 12 results; cheapest 2023 Arenas Moscato $10.49;
    # most expensive 2023 Rewild Sustainable Moscato $19.99.
    judge.check("answer_result_count", contains_count(answer, 12),
                "expected 12 results for the moscato search")
    judge.check("answer_cheapest", contains_phrase(answer, "Arenas Moscato") and contains_money(answer, 10.49),
                "expected cheapest '2023 Arenas Moscato' at $10.49")
    judge.check("answer_most_expensive",
                contains_phrase(answer, "Rewild Sustainable Moscato") and contains_money(answer, 19.99),
                "expected most expensive '2023 Rewild Sustainable Moscato' at $19.99")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
